# core/google_calendar.py

import os
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from django.conf import settings
from .models import GoogleCredential, StudySession

# ตั้งค่า Path ของไฟล์ client_secret.json
CLIENT_SECRETS_FILE = os.path.join(settings.BASE_DIR, "client_secret.json")
SCOPES = ['https://www.googleapis.com/auth/calendar.events']
REDIRECT_URI = 'http://127.0.0.1:8000/google/callback/'

def get_auth_url():
    """สร้าง URL เพื่อส่งผู้ใช้ไป Login Google"""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(prompt='consent')
    return auth_url

def exchange_code_for_token(user, code):
    """นำ Code ที่ได้จาก Google มาแลกเป็น Token ถาวรและบันทึก"""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(code=code)
    creds = flow.credentials

    # แปลง Credentials เป็น Dictionary เพื่อเก็บลง DB
    creds_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }

    GoogleCredential.objects.update_or_create(
        user=user, defaults={'token': creds_data}
    )

def sync_sessions_to_google(user):
    """ฟังก์ชันหลัก: ดึงตารางเรียนไปใส่ Google Calendar"""
    try:
        # 1. ดึง Token จาก DB
        g_cred = GoogleCredential.objects.get(user=user)
        creds = Credentials(**g_cred.token)
        
        # 2. สร้าง Service
        service = build('calendar', 'v3', credentials=creds)

        # 3. หาวิชาที่ยังไม่ได้ซิงค์
        sessions = StudySession.objects.filter(user=user, is_synced=False)
        
        synced_count = 0
        for session in sessions:
            # แปลงเวลาเป็น Format ที่ Google ต้องการ (ISO Format)
            start_time = session.start_time.isoformat()
            end_time = session.end_time.isoformat()
            
            event = {
                'summary': f"อ่าน: {session.subject.name}",
                'description': f"Topic: {session.topic}\n(Created by Smart Study Planner)",
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'Asia/Bangkok', # หรือ 'UTC' ตาม setting
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'Asia/Bangkok',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 10},
                    ],
                },
            }

            try:
                # ยิง API ไปสร้าง Event
                event_result = service.events().insert(calendarId='primary', body=event).execute()
                
                # อัปเดตสถานะใน DB เรา
                session.google_event_id = event_result['id']
                session.is_synced = True
                session.save()
                synced_count += 1
            except Exception as e:
                print(f"Error syncing session {session.session_id}: {e}")

        return True, f"ซิงค์เรียบร้อย {synced_count} รายการ"

    except GoogleCredential.DoesNotExist:
        return False, "ยังไม่ได้เชื่อมต่อบัญชี Google"
    except Exception as e:
        return False, str(e)