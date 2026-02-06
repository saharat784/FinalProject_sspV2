from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        # ดึงแจ้งเตือนทั้งหมดของผู้ใช้ (เอาแค่ 10 อันล่าสุด)
        all_notifs = Notification.objects.filter(recipient=request.user)[:10]
        # นับจำนวนที่ยังไม่อ่าน
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return {
            'notifications': all_notifs,
            'unread_count': unread_count
        }
    return {
        'notifications': [],
        'unread_count': 0
    }