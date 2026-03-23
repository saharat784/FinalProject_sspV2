# core/ai_service.py

import google.generativeai as genai
from django.conf import settings
from django.utils import timezone
import json
import re
import datetime

from core.google_calendar import delete_event_from_google
from .models import Subject, UserAvailability, StudySession

# ตั้งค่า API Key
genai.configure(api_key=settings.GEMINI_API_KEY)

def generate_study_schedule(user, user_settings):
    print("--- เริ่มต้นกระบวนการ AI (Robust Version) ---")

    # 1. ดึงข้อมูลวิชา
    subjects = Subject.objects.filter(user=user)
    if not subjects.exists():
        print("Error: ไม่พบวิชาเรียนในระบบ (กรุณาเพิ่มวิชาก่อน)")
        return False

    subjects_data = []
    for sub in subjects:
        subjects_data.append({
            "name": sub.name,
            "difficulty": sub.get_difficulty_display(),
            "exam_date": sub.exam_date.strftime("%Y-%m-%d %H:%M") if sub.exam_date else "No exam date"
        })
    print(f"ส่งข้อมูลวิชาไป: {[s['name'] for s in subjects_data]}")

    # 2. ดึงข้อมูลเวลาว่าง
    availability = UserAvailability.objects.filter(user=user)
    availability_data = []
    if availability.exists():
        for slot in availability:
            # availability_data.append(f"{slot.get_day_of_week_display()} - {slot.get_time_slot_display()}")
            start_time = f"{slot.hour:02d}:00"
            end_time = f"{(slot.hour + 1) % 24:02d}:00"
            availability_data.append(f"{slot.get_day_of_week_display()}: {start_time} - {end_time}")
        availability_prompt = f"User's available slots: {availability_data}"
    else:
        availability_prompt = "The user has NOT provided specific availability. Please create a balanced schedule."

    # 3. สร้าง Prompt
    now = timezone.localtime(timezone.now())
    current_time_str = now.strftime("%Y-%m-%d %H:%M")
    
    prompt = f"""
    You are an expert study planner. Create a study schedule for a student.
    
    Current Date/Time: {current_time_str} (Do NOT schedule anything before this time).
    
    Configuration:
    - Session Duration: {user_settings.session_duration} minutes per session (the final session may be shorter to fit the remaining time).
    - Break Duration: {user_settings.break_duration} minutes between sessions.
    
    Subjects to study (Source of Truth):
    {json.dumps(subjects_data, ensure_ascii=False)} 

    Availability Constraints:
    {availability_prompt}

    Instructions:
    1. Plan for the next 5 days only.
    2. Return the output STRICTLY as a JSON Array.
    3. Date format MUST be "YYYY-MM-DD HH:MM".
    4. CRITICAL: You MUST use the EXACT subject name provided in the 'Subjects to study' list. 
       - Do NOT paraphrase (e.g., do not change "History of Art" to "Art History").
       - Do NOT abbreviate.
       - Copy the name string exactly character-by-character.
    
    JSON Format required:
    [
        {{
            "subject_name": "Subject Name Here (EXACT MATCH ONLY)",
            "start_time": "YYYY-MM-DD HH:MM", 
            "end_time": "YYYY-MM-DD HH:MM",
            "topic": "Topic to read"
        }}
    ]
    """

    # 4. เรียก Gemini
    model = genai.GenerativeModel('models/gemini-2.5-flash')
    try:
        response = model.generate_content(prompt)
        raw_text = response.text
        print(f"AI Response Raw (First 100 chars): {raw_text[:100]}...")

        # ลบ Markdown Code Block ออก
        cleaned_text = re.sub(r'```json\s*', '', raw_text)
        cleaned_text = re.sub(r'```\s*', '', cleaned_text)
        cleaned_text = cleaned_text.strip()

        # หา List ด้วย Regex
        json_match = re.search(r'\[.*\]', cleaned_text, re.DOTALL)
        if json_match:
            cleaned_text = json_match.group(0)

        # แปลง String เป็น JSON
        try:
            data = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Text that failed: {cleaned_text}")
            return False

        # Normalization: ทำให้เป็น List เสมอ
        schedule_list = []
        if isinstance(data, list):
            schedule_list = data
        elif isinstance(data, dict):
            # ถ้า AI ส่งมาเป็น Object ให้ลองหา Key ที่เป็น List
            for key, value in data.items():
                if isinstance(value, list):
                    schedule_list = value
                    break
        
        if not schedule_list:
             print("Error: แปลง JSON ได้แต่ไม่พบรายการตารางเรียน (Empty List)")
             return False

        print(f"ได้รายการตารางเรียนมาทั้งหมด: {len(schedule_list)} รายการ")

        # บันทึกลง Database
        # ลบ Event เก่าใน Google Calendar
        old_sessions = StudySession.objects.filter(user=user, is_completed=False)
        
        for session in old_sessions:
            # ถ้า Session นี้เคยซิงค์ไปแล้ว ให้ลบออกจาก Google 
            if session.google_event_id:
                delete_event_from_google(user, session.google_event_id)
                
        StudySession.objects.filter(user=user, is_completed=False).delete()

        new_sessions = []
        
        for item in schedule_list:
            subject_name = item.get('subject_name', '').strip()
            
            # ค้นหาวิชา
            subject_obj = subjects.filter(name__iexact=subject_name).first()
            
            if subject_obj:
                try:
                    # แปลงเวลาและใส่ Timezone
                    naive_start = datetime.datetime.strptime(item['start_time'], "%Y-%m-%d %H:%M")
                    naive_end = datetime.datetime.strptime(item['end_time'], "%Y-%m-%d %H:%M")
                    
                    start_t = timezone.make_aware(naive_start)
                    end_t = timezone.make_aware(naive_end)
                    
                    new_sessions.append(StudySession(
                        user=user,
                        subject=subject_obj,
                        start_time=start_t,
                        end_time=end_t,
                        topic=item.get('topic', 'Review')
                    ))
                except ValueError as ve:
                    print(f"Date format error: {ve} in item: {item}")
            else:
                print(f"Warning: วิชา '{subject_name}' ที่ AI บอกมา ไม่มีในฐานข้อมูล")
        
        if new_sessions:
            StudySession.objects.bulk_create(new_sessions)
            print(f"SUCCESS: บันทึกตารางเรียนลง DB สำเร็จ {len(new_sessions)} รายการ")
            return True
        else:
            print("Error: ไม่สามารถสร้าง Session ได้เลย (อาจเพราะชื่อวิชาไม่ตรง)")
            return False

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return False
    

def generate_content_summary(subject_name, topic):
    """
    ฟังก์ชันสำหรับให้ AI สรุปเนื้อหาการเรียน
    """
    try:
        # ถ้าไม่มีหัวข้อ ให้สรุปภาพรวมวิชา
        topic_text = topic if topic else "General concepts"
        
        prompt = f"""
        You are a helpful tutor. Summarize the key takeaways for the topic: "{topic_text}" 
        in the subject: "{subject_name}".
        
        Instructions:
        1. Summarize in Thai language.
        2. Keep it concise (around 3-5 bullet points).
        3. Make it encouraging.
        4. Use HTML tags for formatting (e.g., <ul>, <li>, <strong>).
        
        Example Output format:
        <ul>
            <li><strong>Point 1:</strong> Detail...</li>
            <li><strong>Point 2:</strong> Detail...</li>
        </ul>
        <p>Keep up the good work!</p>
        """

        model = genai.GenerativeModel('models/gemini-2.5-flash') # หรือรุ่นที่คุณใช้ได้
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        print(f"AI Summary Error: {e}")
        return "<p>ขออภัย ไม่สามารถสรุปเนื้อหาได้ในขณะนี้ (AI Error)</p>"
    

def generate_quiz_questions(subject_name, topic):
    print(f"--- 🚀 AI Quiz Start: {subject_name} ---") # เพิ่ม Log บรรทัดนี้เพื่อเช็คว่าโค้ดถูกเรียกจริง

    try:
        topic_text = topic if topic else "General concepts"
        
        prompt = f"""
        Create a multiple-choice quiz for the subject "{subject_name}", topic: "{topic_text}".
        
        Instructions:
        1. Create exactly 5 questions.
        2. Language: Thai (ภาษาไทย).
        3. Difficulty: Moderate.
        4. Return ONLY a JSON Array. No Markdown. No Intro text.
        
        JSON Format Example:
        [
            {{
                "question": "คำถาม?",
                "options": ["ก", "ข", "ค", "ง"],
                "correct_index": 0
            }}
        ]
        """

        model = genai.GenerativeModel('models/gemini-2.5-flash') 
        
        response = model.generate_content(prompt)
        raw_text = response.text
        
        print(f"DEBUG RAW AI: {raw_text[:50]}...") # ดูว่า AI ตอบกลับมาไหม

        # ใช้ Regex แกะ JSON ต้องมี import re ข้างบนสุด
        match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        
        if match:
            json_str = match.group(0)
            json_str = json_str.replace("`", "") 
            return json.loads(json_str)
        else:
            print("Error: AI ไม่ได้ส่ง JSON Array มา")
            return None

    except Exception as e:
        print(f"AI Quiz Error: {e}") # Log นี้สำคัญมาก
        return None