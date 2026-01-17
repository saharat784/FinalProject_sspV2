from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv() # สั่งให้โหลดค่าจากไฟล์ .env

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG') == 'True'

# AI Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = ['https://smart-study-planner-wa6t.onrender.com']

if DEBUG:
    # สำหรับ Localhost (แก้ typo ให้แล้ว)
    LOGIN_REDIRECT_URI = 'http://127.0.0.1:8000/google/login/callback/'
else:
    # สำหรับ Render (Production)
    LOGIN_REDIRECT_URI = 'https://smart-study-planner-wa6t.onrender.com/google/login/callback/'

# LOGIN_REDIRECT_URI = 'https://http://127.0.0.1:8000/google/login/callback/' # สำหรับทดสอบบนเครื่อง localhost

# LOGIN_REDIRECT_URI = 'https://smart-study-planner-wa6t.onrender.com/google/login/callback/' # สำหรับใช้งานจริงบน Render

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Application definition

INSTALLED_APPS = [
    'cloudinary_storage',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'widget_tweaks',
    'cloudinary',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # ✅ เพิ่มบรรทัดนี้ (ต้องอยู่ต่อจาก SecurityMiddleware ทันที)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'smart_study_planner.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'core', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'smart_study_planner.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# smart_study_planner/settings.py

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.getenv('DB_NAME'),   # ชื่อฐานข้อมูลที่คุณสร้าง
#         'USER': os.getenv('DB_USER'),     # ชื่อผู้ใช้ PostgreSQL
#         'PASSWORD': os.getenv('DB_PASSWORD'),    # รหัสผ่าน PostgreSQL
#         'HOST': os.getenv('DB_HOST'),    # หรือ IP address ของฐานข้อมูล
#         'PORT': os.getenv('DB_PORT'),       # Port มาตรฐานของ PostgreSQL
#     }
# }

DATABASES = {
    'default': dj_database_url.config(
        # บรรทัดนี้สำคัญ: มันจะเช็คว่าถ้ามี DATABASE_URL (บน Render) ให้ใช้
        # แต่ถ้าไม่มี (บนเครื่องเรา) ให้กลับไปใช้ SQLite เหมือนเดิม ไม่ต้องแก้ไปแก้มา
        default=os.getenv('DATABASE_URL', 'sqlite:///db.sqlite3'),
        conn_max_age=600
    )
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Bangkok'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
# โฟลเดอร์ที่จะรวบรวมไฟล์ CSS/JS ทั้งหมดไปกองรวมกัน
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles') 
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'core/static')
]

# MEDIA_URL = '/media/'
# MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'core.CustomUser'

AUTHENTICATION_BACKENDS = [
    'core.backends.EmailBackend', 
    'django.contrib.auth.backends.ModelBackend', 
]

# บอก Django ว่าหน้า Login ของเราคือ path ที่ชื่อ 'login' หรือ '/login/'
LOGIN_URL = 'login' 

# (ทางเลือก) บอกว่าจะให้เด้งไปไหนถ้า Login สำเร็จแล้วไม่มี parameter next
LOGIN_REDIRECT_URL = 'home_page'

# --- Cloudinary Settings ---
# CLOUDINARY_STORAGE = {
#     'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
#     'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
#     'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
# }

if 'RENDER' in os.environ:
    print("--- 🟢 Using Cloudinary for BOTH Media & Static ---")

    STORAGES = {
        "default": {
            # เก็บรูปภาพที่อัปโหลด
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            # เก็บไฟล์ CSS/JS ของเว็บ (ใช้ Cloudinary แทน Whitenoise)
            "BACKEND": "cloudinary_storage.storage.StaticHashedCloudinaryStorage",
        },
    }
else:
    print("--- 🏠 Using Local File Storage ---")

    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    
# บอก Django ว่าถ้ามีการอัปโหลดไฟล์ (Media) ให้ไปเก็บที่ Cloudinary
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'