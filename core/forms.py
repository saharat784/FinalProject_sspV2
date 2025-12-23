# core/forms.py

import os
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser, Subject, UserSettings

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = UserCreationForm.Meta.fields + ('email',)

class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': 'Username or Email'}
        )
        self.fields['password'].widget.attrs.update(
            {'class': 'form-control', 'placeholder': 'Password'}
        )

class SubjectForm(forms.ModelForm):
    # ใช้ Widget ที่สร้างใหม่
    file = forms.FileField(
        widget=MultipleFileInput(attrs={'class': 'form-control', 'multiple': True}),
        label='ไฟล์ประกอบการเรียน (สูงสุด 5 ไฟล์)',
        required=False
    )

    class Meta:
        model = Subject
        fields = ['name', 'difficulty', 'exam_date'] 
        widgets = {
            'exam_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'}
            ),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'difficulty': forms.Select(attrs={'class': 'form-control'}),
        }

    # เพิ่มฟังก์ชันตรวจสอบความถูกต้องของไฟล์
    def clean_files(self):
        file = self.files.getlist('files')
        
        if len(file) > 5:
            raise forms.ValidationError("อัปโหลดได้สูงสุด 5 ไฟล์ต่อวิชา")

        valid_extensions = ['.pdf', '.docx', '.pptx', '.txt']
        max_size = 10 * 1024 * 1024 # 10 MB

        for f in file:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError(f"ไม่รองรับไฟล์ {f.name} (รองรับเฉพาะ .pdf, .docx, .pptx, .txt)")
            
            if f.size > max_size:
                raise forms.ValidationError(f"ไฟล์ {f.name} มีขนาดใหญ่เกิน 10MB")

        return file

class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = ['session_duration', 'break_duration', 'notifications_enabled']