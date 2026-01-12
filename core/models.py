# core/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

# ตารางผู้ใช้ (Users)
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True) # เพิ่มบรรทัดนี้
    # ✅ เพิ่ม: รูปโปรไฟล์ (เก็บไฟล์จริง)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    class Meta:
        db_table = 'users'

# ตารางการตั้งค่าของผู้ใช้ (UserSettings)
class UserSettings(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    session_duration = models.IntegerField(default=60)
    break_duration = models.IntegerField(default=10)
    notifications_enabled = models.BooleanField(default=True)
    # ✅ เพิ่ม: ข้อมูลโปรไฟล์เพิ่มเติม
    bio = models.CharField(max_length=255, blank=True, null=True, verbose_name="คติประจำใจ")
    academic_goal = models.CharField(max_length=255, blank=True, null=True, verbose_name="เป้าหมายการเรียน (เช่น GPA 4.00)")

    def __str__(self):
        return f"Settings for {self.user.username}"
    
# ตารางเก็บ Credential ของ Google OAuth2
class GoogleCredential(models.Model):
    """เก็บ Token ของผู้ใช้เพื่อไม่ต้อง Login Google ใหม่ทุกครั้ง"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    token = models.JSONField() # เก็บ token, refresh_token
    created_at = models.DateTimeField(auto_now_add=True)

# ตารางวิชา (Subjects)
class Subject(models.Model):
    DIFFICULTY_CHOICES = [
        (1, 'ง่าย'), (2, 'ปานกลาง'), (3, 'ยาก'),
    ]
    IMPORTANCE_CHOICES = [
        (1, 'น้อย'), (2, 'ปานกลาง'), (3, 'มาก'),
    ]
    subject_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    difficulty = models.IntegerField(choices=DIFFICULTY_CHOICES, default=2)
    importance = models.IntegerField(choices=IMPORTANCE_CHOICES, default=2)
    exam_date = models.DateTimeField()
    file = models.FileField(upload_to='subject_files/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subjects'

    def __str__(self):
        return self.name

# ตารางไฟล์ (Files)
class File(models.Model):
    file_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, related_name='subject_files')
    
    # เปลี่ยนจาก URLField เป็น FileField เพื่อเก็บไฟล์จริง
    file = models.FileField(upload_to='subject_materials/') 
    
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=255)
    size_in_bytes = models.BigIntegerField()
    
    # เพิ่มลำดับ
    order = models.PositiveIntegerField(default=1) 
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'files'
        ordering = ['order'] # สั่งให้เรียงตามลำดับเสมอ

# ตารางแผนการอ่าน (StudyPlans)
class StudyPlan(models.Model):
    plan_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'study_plans'

# ตารางกิจกรรมในแผน (PlanActivities)
class PlanActivity(models.Model):
    activity_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    description = models.TextField()
    status = models.CharField(max_length=50)
    is_break = models.BooleanField(default=False)
    note = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'plan_activities'

# ตารางแบบทดสอบ (Quizzes)
class Quiz(models.Model):
    quiz_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(PlanActivity, on_delete=models.CASCADE)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    questions = models.JSONField()
    user_answers = models.JSONField(null=True, blank=True)
    score = models.IntegerField(null=True, blank=True)
    taken_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quizzes'

# ตารางการวิเคราะห์ความก้าวหน้า (ProgressAnalytics)
class ProgressAnalytic(models.Model):
    analytic_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    date = models.DateField()
    time_spent_actual = models.IntegerField()
    time_spent_planned = models.IntegerField()
    completion_percentage = models.FloatField()
    study_streak_count = models.IntegerField()

    class Meta:
        db_table = 'progress_analytics'

# ตารางเก็บเวลาว่างของผู้ใช้
class UserAvailability(models.Model):
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ]
    TIMESLOT_CHOICES = [
        ('morning', '06:00-12:00'),
        ('afternoon', '13:00-18:00'),
        ('evening', '18:00-22:00'),
        ('night', '22:00-02:00'),
    ]
    availability_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    time_slot = models.CharField(max_length=10, choices=TIMESLOT_CHOICES)

    class Meta:
        unique_together = ('user', 'day_of_week', 'time_slot')

    def __str__(self):
        return f"{self.user.username} - {self.get_day_of_week_display()} - {self.time_slot}"
    
# ตารางเซสชันการเรียน (StudySessions)
class StudySession(models.Model):
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    topic = models.CharField(max_length=255, blank=True, null=True) # หัวข้อที่จะอ่าน (ถ้า AI ระบุมาให้)
    is_completed = models.BooleanField(default=False)

    class Meta:
        db_table = 'study_sessions'
        ordering = ['start_time']

    def __str__(self):
        return f"{self.subject.name} ({self.start_time})"
    
    google_event_id = models.CharField(max_length=255, blank=True, null=True)
    is_synced = models.BooleanField(default=False)
    
# ตารางสรุปการเรียน (StudySummaries)
class StudySummary(models.Model):
    summary_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    session = models.OneToOneField(StudySession, on_delete=models.CASCADE, related_name='summary') # 1 Session มี 1 สรุป
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    content = models.TextField() # เก็บ HTML ที่ AI ส่งมา
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'study_summaries'
        ordering = ['-created_at']

    def __str__(self):
        return f"Summary: {self.subject.name} - {self.created_at}"

# ตารางผลลัพธ์แบบทดสอบ (QuizResults)
class QuizResult(models.Model):
    result_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    session = models.ForeignKey(StudySession, on_delete=models.CASCADE)
    
    # เก็บข้อมูลโจทย์และคำตอบเป็น JSON (เพราะโจทย์เปลี่ยนไปเรื่อยๆ ตาม AI)
    questions_data = models.JSONField()  # โจทย์ + ตัวเลือก + เฉลย
    user_answers = models.JSONField()    # คำตอบที่ผู้ใช้เลือก (List of indices)
    
    score = models.IntegerField()
    total_questions = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quiz_results'
        ordering = ['-created_at']