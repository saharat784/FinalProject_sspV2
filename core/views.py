# core/views.py

from datetime import timedelta, datetime
import json
import os
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone # ใช้ timezone
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from datetime import timedelta, datetime, date
from django.contrib import messages
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
from google_auth_oauthlib.flow import Flow
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.contrib.auth import login
from django.conf import settings

from core.google_calendar import exchange_code_for_token, get_auth_url, sync_sessions_to_google
from smart_study_planner import settings

from .forms import CustomUserCreationForm, CustomAuthenticationForm, SubjectForm, UserSettingsForm
from .models import CustomUser, File, QuizResult, StudySummary, Subject, UserAvailability, UserSettings, StudySession
from .ai_service import generate_content_summary, generate_quiz_questions, generate_study_schedule

# ตั้งค่า Path (ใช้ตัวเดียวกับที่มีอยู่)
CLIENT_SECRETS_FILE = os.path.join(settings.BASE_DIR, "client_secret.json")

# Scopes สำหรับ Login (ขอแค่ข้อมูลพื้นฐาน)
LOGIN_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]
LOGIN_REDIRECT_URI = 'http://127.0.0.1:8000/google/login/callback/'

def landing_page_view(request):
    return render(request, 'core/landing_page.html')

def google_login_start(request):
    """ส่งผู้ใช้ไปหน้า Google Login"""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=LOGIN_SCOPES,
        redirect_uri=LOGIN_REDIRECT_URI
    )
    
    auth_url, state = flow.authorization_url(prompt='select_account')
    
    # เก็บ State ไว้เช็คความปลอดภัย
    request.session['google_oauth_state'] = state
    return redirect(auth_url)

def google_login_callback(request):
    """รับ Code จาก Google และทำการ Login/Register"""
    state = request.session.get('google_oauth_state')
    
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=LOGIN_SCOPES,
            redirect_uri=LOGIN_REDIRECT_URI,
            state=state
        )
        
        # แปลง Code เป็น Token
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        credentials = flow.credentials
        
        # แกะข้อมูลผู้ใช้จาก ID Token (JWT)
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            google_requests.Request(),
            audience=credentials.client_id
        )
        
        email = id_info.get('email')
        first_name = id_info.get('given_name', '')
        last_name = id_info.get('family_name', '')
        
        # --- Logic การ Login/Register ---
        if email:
            # 1. เช็คว่ามี User นี้ในระบบไหม?
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                # 2. ถ้าไม่มี -> สร้าง User ใหม่ (Register)
                # สร้าง username จาก email (ตัด @...)
                username = email.split('@')[0]
                
                # ตรวจสอบว่า username ซ้ำไหม ถ้าซ้ำให้เติมตัวเลข
                base_username = username
                counter = 1
                while CustomUser.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                user = CustomUser.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name
                )
                # เนื่องจาก Login ผ่าน Google จึงไม่มี password เราปล่อยไว้ได้ หรือ set unusable
                user.set_unusable_password()
                user.save()
            
            # 3. Login เข้าสู่ระบบ
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('home_page')
            
    except Exception as e:
        messages.error(request, f"Google Login Failed: {str(e)}")
        
    return redirect('login')

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('login')  
    else:
        form = CustomUserCreationForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                login(request, user)
                return redirect('home_page')
            else:
                messages.error(request, 'อีเมลหรือรหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

@login_required
def homepage_view(request):
    user = request.user
    # today = timezone.now().date()
    # now = timezone.now()
    local_now = timezone.localtime(timezone.now()) 
    today = local_now.date()
    now = local_now

    # รับค่าวันที่จาก URL ถ้าไม่มีให้ใช้ "วันนี้"
    date_param = request.GET.get('date')
    if date_param:
        try:
            current_date = datetime.strptime(date_param, '%Y-%m-%d').date()
        except ValueError:
            current_date = today
    else:
        current_date = today

    # หาวันอาทิตย์ที่เป็นจุดเริ่มต้นของสัปดาห์นี้ (Sunday start)
    # (isoweekday: Mon=1...Sun=7). ถ้าวันนี้เป็น Sun(7) start = today. 
    # สูตร: current_date - timedelta(days=current_date.isoweekday() % 7)
    # ใส่ int() ครอบ current_date.strftime("%w")
    start_of_week = current_date - timedelta(days=int(current_date.strftime("%w")))
    end_of_week = start_of_week + timedelta(days=6)

    # สร้าง List วันที่ในสัปดาห์ (อาทิตย์ - เสาร์) เพื่อใช้ทำหัวตาราง
    week_dates = []
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        week_dates.append(day)

    # ดึงข้อมูล Session ในสัปดาห์นั้นมา
    weekly_sessions = StudySession.objects.filter(
        user=user,
        start_time__date__gte=start_of_week,
        start_time__date__lte=end_of_week
    )

    # สร้างตาราง Grid (Time Slots) ตั้งแต่ 06:00 - 23:00 (ปรับช่วงเวลาได้ตามต้องการ)
    hours_range = range(6, 24) # 6 โมงเช้า ถึง เที่ยงคืน
    calendar_grid = []

    for hour in hours_range:
        row = {'hour': f"{hour:02d}:00", 'days': []}
        for day in week_dates:
            # หาวิชาที่เรียนในวันนั้น และ ชั่วโมงนั้น
            # หมายเหตุ: Logic นี้แบบง่าย เช็คเฉพาะชั่วโมงเริ่มต้น
            sessions_in_slot = []
            for s in weekly_sessions:
                # แปลงเป็น local time ก่อนเทียบ
                local_start = timezone.localtime(s.start_time)
                if local_start.date() == day and local_start.hour == hour:
                    sessions_in_slot.append(s)
            
            row['days'].append({
                'date': day,
                'sessions': sessions_in_slot
            })
        calendar_grid.append(row)

    today_sessions = StudySession.objects.filter(user=user, start_time__date=today).order_by('start_time')
    total_today = today_sessions.count()
    completed_today = today_sessions.filter(is_completed=True).count()
    
    daily_progress = int((completed_today / total_today) * 100) if total_today > 0 else 0

    next_session = today_sessions.filter(is_completed=False).first()
    
    # 2. ข้อมูลตารางเรียนทั้งหมด (Upcoming)
    upcoming_sessions = StudySession.objects.filter(
        user=user, 
        start_time__gte=now - timedelta(days=1) 
    ).order_by('start_time')[:20] 

    # 3. ข้อมูลสถิติ
    total_subjects = Subject.objects.filter(user=user).count()
    total_plans = StudySession.objects.filter(user=user).count()
    
    completed_all = StudySession.objects.filter(user=user, is_completed=True).count()
    readiness_score = int((completed_all / total_plans) * 100) if total_plans > 0 else 0

    upcoming_exams = Subject.objects.filter(user=user, exam_date__gte=now).order_by('exam_date')
    exams_data = []
    for subject in upcoming_exams:
        days_left = (subject.exam_date.date() - today).days
        exams_data.append({'name': subject.name, 'date': subject.exam_date, 'days_left': days_left,})

    context = {
        'user': user,
        'today_sessions': today_sessions,
        'daily_progress': daily_progress,
        'next_session': next_session,
        # ส่งข้อมูล Calendar ไปใหม่
        'calendar_grid': calendar_grid, 
        'week_dates': week_dates,
        'current_date_str': current_date.strftime('%Y-%m-%d'),
        # ข้อมูลเดิม
        'total_subjects': total_subjects,
        'total_plans': total_plans,
        'readiness_score': readiness_score,
        'exams_data': exams_data,
    }
    return render(request, 'core/home_page.html', context)

@login_required
def add_subject_view(request):
    # ดึงวิชาและไฟล์มาแสดง
    subjects = Subject.objects.filter(user=request.user).order_by('-created_at').prefetch_related('subject_files')

    if request.method == 'POST':
        form = SubjectForm(request.POST, request.FILES)
        if form.is_valid():
            # 1. บันทึกวิชา
            subject = form.save(commit=False)
            subject.user = request.user
            subject.save()

            # 2. จัดการไฟล์
            files = request.FILES.getlist('files')
            
            # เช็คโควต้าว่าถ้ารวมของเดิมแล้วเกิน 5 ไหม (เผื่อในอนาคตมี Edit)
            current_files_count = File.objects.filter(subject=subject).count()
            
            for index, f in enumerate(files):
                if current_files_count + index + 1 > 5:
                    break # หยุดถ้าเกิน 5

                # สร้าง File object
                File.objects.create(
                    subject=subject,
                    file=f,
                    file_name=f.name,
                    file_type=f.content_type,
                    size_in_bytes=f.size,
                    order=index + 1 # ลำดับเริ่มที่ 1
                )
            
            return redirect('add_subject')
    else:
        form = SubjectForm()

    context = {
        'form': form,
        'subjects': subjects
    }
    return render(request, 'core/add_subject.html', context)

@login_required
def delete_subject_view(request, subject_id):
    subject = get_object_or_404(Subject, subject_id=subject_id, user=request.user)
    if request.method == 'POST':
        subject.delete()
        return redirect('add_subject')
    return redirect('add_subject')

@login_required
def delete_file_view(request, file_id):
    # 1. ดึงไฟล์ที่ต้องการลบ (เช็ค user เพื่อความปลอดภัย)
    file_obj = get_object_or_404(File, file_id=file_id, subject__user=request.user)
    subject = file_obj.subject
    
    # 2. ลบไฟล์ (ไฟล์จริงจะหายไปเพราะ Django จัดการให้ หรือต้องใช้ Library cleanup)
    file_obj.delete()
    
    # 3. Reorder Logic: เรียงลำดับไฟล์ที่เหลือใหม่
    remaining_files = File.objects.filter(subject=subject).order_by('uploaded_at') # เรียงตามเวลาที่อัป
    
    for index, f in enumerate(remaining_files):
        f.order = index + 1 # รันเลขใหม่เริ่มจาก 1
        f.save()
        
    messages.success(request, 'ลบไฟล์เรียบร้อยแล้ว')
    return redirect('add_subject')

@login_required
def set_schedule_view(request):
    existing_slots = UserAvailability.objects.filter(user=request.user)
    selected_slots = set(f"{slot.day_of_week}_{slot.time_slot}" for slot in existing_slots)

    days_of_week = {
        0: 'จันทร์', 1: 'อังคาร', 2: 'พุธ',
        3: 'พฤหัสบดี', 4: 'ศุกร์', 5: 'เสาร์', 6: 'อาทิตย์'
    }
    
    # แก้ไขให้เป็น List of Dict เพื่อให้ Template ใช้งานได้ง่าย ({{ slot.id }}, {{ slot.class }})
    time_slots_data = [
        {'id': 'morning', 'class': 'morning', 'label': 'ช่วงเช้า (06:00-12:00)'},
        {'id': 'afternoon', 'class': 'afternoon', 'label': 'ช่วงบ่าย (13:00-18:00)'},
        {'id': 'evening', 'class': 'evening', 'label': 'ช่วงเย็น (18:00-22:00)'},
        {'id': 'night', 'class': 'night', 'label': 'ช่วงดึก (22:00-02:00)'},
    ]

    if request.method == 'POST':
        new_selections_keys = [key for key in request.POST.keys() if key.startswith('slot_')]
        
        UserAvailability.objects.filter(user=request.user).delete()
        slots_to_create = []
        for key in new_selections_keys:
            parts = key.split('_')
            # ป้องกัน Error ถ้า split แล้วได้ค่าไม่ครบ
            if len(parts) == 3:
                _, day, slot = parts
                slots_to_create.append(
                    UserAvailability(user=request.user, day_of_week=int(day), time_slot=slot)
                )
        UserAvailability.objects.bulk_create(slots_to_create)
        return redirect('study_settings')

    context = {
        'user_selections': selected_slots,
        'days': days_of_week, 
        'time_slots': time_slots_data, 
    }
    return render(request, 'core/set_schedule.html', context)

@login_required
def study_settings_view(request):
    # เหลือฟังก์ชันเดียวที่มี Logic ครบถ้วน
    settings, created = UserSettings.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            user_settings = form.save() # บันทึกค่า settings ก่อน
            
            # --- เริ่มกระบวนการ AI ---
            # messages.info(request, 'กำลังประมวลผลและสร้างตารางเรียนด้วย AI กรุณารอสักครู่...')
            
            success = generate_study_schedule(request.user, user_settings)
            
            if success:
                messages.success(request, 'สร้างตารางเรียนเรียบร้อยแล้ว!')
            else:
                messages.warning(request, 'บันทึกการตั้งค่าแล้ว แต่เกิดข้อผิดพลาดในการสร้างตาราง (อาจไม่มีข้อมูลวิชา หรือ AI มีปัญหา)')
            
            return redirect('home_page')
    else:
        form = UserSettingsForm(instance=settings)

    context = {
        'form': form
    }
    return render(request, 'core/study_settings.html', context)

@login_required
def toggle_session_complete(request, session_id):
    session = get_object_or_404(StudySession, session_id=session_id, user=request.user)
    session.is_completed = not session.is_completed
    session.save()
    return redirect('home_page')

@login_required
def start_studying_view(request, session_id):
    # ดึงข้อมูล Session ที่จะเรียน
    session = get_object_or_404(StudySession, session_id=session_id, user=request.user)
    
    # ดึงการตั้งค่า (เพื่อเอาเวลาพัก)
    settings, _ = UserSettings.objects.get_or_create(user=request.user)
    
    # คำนวณระยะเวลาเรียนเป็นนาที
    duration = (session.end_time - session.start_time).total_seconds() / 60
    
    # (Optional) คำนวณความคืบหน้าของวิชานี้ (สมมติ)
    # อาจจะดึงจาก ProgressAnalytic หรือคำนวณสดๆ ก็ได้
    subject_progress = 0 # ใส่ Logic คำนวณจริงตรงนี้ถ้ามี
    
    context = {
        'session': session,
        'duration_minutes': int(duration),
        'break_minutes': settings.break_duration,
        'subject_progress': subject_progress,
    }
    return render(request, 'core/start_studying.html', context)

@login_required
def complete_session_view(request, session_id):
    # 1. บันทึกสถานะว่าเรียนจบ
    session = get_object_or_404(StudySession, session_id=session_id, user=request.user)
    session.is_completed = True
    session.save()
    
    # 2. Redirect ไปยังหน้าแสดงผลลัพธ์ (Finished Page)
    return redirect('finished_studying', session_id=session.session_id)

@login_required
def finished_studying_view(request, session_id):
    session = get_object_or_404(StudySession, session_id=session_id, user=request.user)
    settings, _ = UserSettings.objects.get_or_create(user=request.user)
    
    # คำนวณระยะเวลา (นาที)
    duration = (session.end_time - session.start_time).total_seconds() / 60
    
    context = {
        'session': session,
        'duration_minutes': int(duration),
        'break_minutes': settings.break_duration,
    }
    return render(request, 'core/finished_studying.html', context)

@login_required
def get_session_summary(request, session_id):
    """
    API สำหรับเรียก AI สรุปเนื้อหาและบันทึกลง DB (ใช้คู่กับ Popup Loading)
    """
    if request.method == 'GET':
        try:
            session = get_object_or_404(StudySession, session_id=session_id, user=request.user)
            
            # 1. เช็คว่ามีสรุปเดิมอยู่แล้วไหม
            summary_obj, created = StudySummary.objects.get_or_create(
                session=session,
                defaults={
                    'user': request.user,
                    'subject': session.subject,
                    'content': ''
                }
            )

            # 2. ถ้ายังไม่มีเนื้อหา ให้เรียก AI สร้างใหม่และบันทึก
            if not summary_obj.content:
                ai_content = generate_content_summary(session.subject.name, session.topic)
                summary_obj.content = ai_content
                summary_obj.save()
            
            # 3. ส่งผลลัพธ์กลับว่า "เสร็จแล้ว" (ไม่ต้องส่ง content กลับไป เพราะเดี๋ยวจะ redirect ไปดูหน้าเต็ม)
            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def study_summary_view(request, session_id):
    """
    หน้าแสดงสรุปเนื้อหา (แยกออกมาเป็นหน้าใหม่)
    """
    session = get_object_or_404(StudySession, session_id=session_id, user=request.user)
    
    # 1. เช็คว่ามีสรุปอยู่แล้วหรือไม่?
    summary_obj, created = StudySummary.objects.get_or_create(
        session=session,
        defaults={
            'user': request.user,
            'subject': session.subject,
            'content': '' # สร้างไว้ก่อน เดี๋ยวเติม
        }
    )

    # 2. ถ้าเพิ่งสร้าง (ยังไม่มีเนื้อหา) หรือเนื้อหาว่างเปล่า -> ให้ AI สรุป
    if created or not summary_obj.content:
        # เรียก AI
        ai_content = generate_content_summary(session.subject.name, session.topic)
        
        # บันทึกลง DB
        summary_obj.content = ai_content
        summary_obj.save()

    return render(request, 'core/summary_detail.html', {'summary': summary_obj})

@login_required
def summary_history_view(request):
    """
    หน้ารวมรายการสรุปทั้งหมดที่เคยทำ
    """
    summaries = StudySummary.objects.filter(user=request.user).select_related('subject')
    return render(request, 'core/summary_list.html', {'summaries': summaries})

@login_required
def get_session_quiz(request, session_id):
    if request.method == 'GET':
        try:
            session = StudySession.objects.get(session_id=session_id, user=request.user)
            # เรียก AI สร้างโจทย์
            quiz_data = generate_quiz_questions(session.subject.name, session.topic)
            
            if quiz_data:
                return JsonResponse({'success': True, 'quiz': quiz_data})
            else:
                return JsonResponse({'success': False, 'error': 'AI could not generate quiz'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
@require_POST
def submit_quiz_view(request):
    """
    API รับข้อมูลการสอบ บันทึก และส่งคืน URL สำหรับ redirect
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        questions = data.get('questions') # โจทย์ที่ AI สร้าง (ส่งกลับมาบันทึก)
        user_answers = data.get('answers') # คำตอบที่ user เลือก (Array of int)

        session = get_object_or_404(StudySession, session_id=session_id, user=request.user)

        # คำนวณคะแนน Server-side
        score = 0
        for i, q in enumerate(questions):
            # ตรวจว่าตอบถูกไหม (เทียบ user_answers[i] กับ correct_index)
            # ต้องระวังเรื่อง index out of range หรือค่าว่าง
            user_ans = user_answers[i]
            if user_ans is not None and int(user_ans) == int(q['correct_index']):
                score += 1

        # บันทึกลง DB
        quiz_result = QuizResult.objects.create(
            user=request.user,
            session=session,
            questions_data=questions,
            user_answers=user_answers,
            score=score,
            total_questions=len(questions)
        )

        return JsonResponse({
            'success': True, 
            'redirect_url': reverse('quiz_result', args=[quiz_result.result_id])
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def quiz_result_view(request, result_id):
    """ หน้าแสดงผลคะแนน """
    result = get_object_or_404(QuizResult, result_id=result_id, user=request.user)
    percentage = int((result.score / result.total_questions) * 100)
    
    return render(request, 'core/quiz_result.html', {
        'result': result,
        'percentage': percentage
    })

@login_required
def quiz_solution_view(request, result_id):
    """ หน้าดูเฉลยละเอียด """
    result = get_object_or_404(QuizResult, result_id=result_id, user=request.user)
    
    # รวมข้อมูลโจทย์และคำตอบผู้ใช้ เพื่อส่งไปวนลูปใน Template ได้ง่ายๆ
    solution_data = []
    for i, q in enumerate(result.questions_data):
        user_ans_index = result.user_answers[i]
        solution_data.append({
            'question': q['question'],
            'options': q['options'],
            'correct_index': q['correct_index'],
            'user_index': user_ans_index,
            'is_correct': (user_ans_index is not None) and (int(user_ans_index) == int(q['correct_index']))
        })

    return render(request, 'core/quiz_solution.html', {
        'result': result,
        'solution_data': solution_data
    })

@login_required
def google_auth_start(request):
    """เริ่มกระบวนการขอสิทธิ์ Google"""
    auth_url = get_auth_url()
    return redirect(auth_url)

@login_required
def google_auth_callback(request):
    """Google ส่งผู้ใช้กลับมาที่นี่พร้อม Code"""
    code = request.GET.get('code')
    if code:
        try:
            exchange_code_for_token(request.user, code)
            messages.success(request, 'เชื่อมต่อ Google Calendar สำเร็จ!')
            
            # พอเชื่อมต่อเสร็จ ให้ซิงค์ทันทีเลย
            return redirect('sync_calendar')
            
        except Exception as e:
            messages.error(request, f'เกิดข้อผิดพลาด: {e}')
    
    return redirect('home_page')

@login_required
def sync_calendar_view(request):
    """กดปุ่มซิงค์"""
    success, msg = sync_sessions_to_google(request.user)
    
    if not success and "ยังไม่ได้เชื่อมต่อ" in msg:
        # ถ้ายังไม่เคย Login ให้ส่งไปหน้า Login Google
        return redirect('google_auth_start')
    
    if success:
        messages.success(request, f"Sync Success: {msg}")
    else:
        messages.error(request, f"Sync Error: {msg}")
        
    return redirect('home_page')

def logout_view(request):
    logout(request)
    return redirect('login')

