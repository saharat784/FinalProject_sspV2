#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# รวบรวมไฟล์ Static ไปไว้ใน folder staticfiles
python manage.py collectstatic --no-input

# อัปเดต Database (Migrate)
python manage.py migrate