# check_api.py
import google.generativeai as genai

# ใส่ API Key ของคุณลงไปตรงนี้
API_KEY = "AIzaSyB1bOjn2BzljmtlQ5XtrMcjkbghOFXrxsA" 

genai.configure(api_key=API_KEY)

print("--- กำลังตรวจสอบรายชื่อโมเดล... ---")
try:
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- พบโมเดล: {m.name}")
            available_models.append(m.name)
    
    if not available_models:
        print("❌ ไม่พบโมเดลเลย (ตรวจสอบ API Key หรือสิทธิ์การใช้งาน)")
    else:
        print(f"✅ พบทั้งหมด {len(available_models)} โมเดล")

except Exception as e:
    print(f"❌ เกิดข้อผิดพลาด: {e}")