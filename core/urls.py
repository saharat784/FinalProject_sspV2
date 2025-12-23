# core/urls.py

from django.urls import path
from .views import register_view, login_view, homepage_view, logout_view, landing_page_view, toggle_session_complete
from core import views

urlpatterns = [
    path('', landing_page_view, name='landing_page'),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    # Google OAuth2 URLs
    path('google/login-start/', views.google_login_start, name='google_login_start'),
    path('google/login/callback/', views.google_login_callback, name='google_login_callback'),
    # Main Application URLs
    path('home/', homepage_view, name='home_page'),
    path('add-subject/', views.add_subject_view, name='add_subject'),
    path('delete-subject/<uuid:subject_id>/', views.delete_subject_view, name='delete_subject'),
    path('delete-file/<uuid:file_id>/', views.delete_file_view, name='delete_file'),
    path('set-schedule/', views.set_schedule_view, name='set_schedule'),
    path('study-settings/', views.study_settings_view, name='study_settings'),
    path('toggle-session/<uuid:session_id>/', toggle_session_complete, name='toggle_session_complete'),
    path('start-studying/<uuid:session_id>/', views.start_studying_view, name='start_studying'),
    path('finished-studying/<uuid:session_id>/', views.finished_studying_view, name='finished_studying'),
    path('complete-session/<uuid:session_id>/', views.complete_session_view, name='complete_session'),
    # summary URLs
    path('api/get-summary/<uuid:session_id>/', views.get_session_summary, name='get_session_summary'),
    path('summary/<uuid:session_id>/', views.study_summary_view, name='study_summary'),
    path('my-summaries/', views.summary_history_view, name='summary_history'),
    # quiz URLs
    path('api/get-quiz/<uuid:session_id>/', views.get_session_quiz, name='get_session_quiz'),
    path('api/submit-quiz/', views.submit_quiz_view, name='submit_quiz'),
    path('quiz-result/<uuid:result_id>/', views.quiz_result_view, name='quiz_result'),
    path('quiz-solution/<uuid:result_id>/', views.quiz_solution_view, name='quiz_solution'),
    path('logout/', logout_view, name='logout'),
    # Google Calendar Integration URLs
    path('google/login/', views.google_auth_start, name='google_auth_start'),
    path('google/callback/', views.google_auth_callback, name='google_auth_callback'),
    path('sync-calendar/', views.sync_calendar_view, name='sync_calendar'),
]