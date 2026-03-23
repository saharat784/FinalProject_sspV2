from django.contrib import admin
from .models import Feedback, CustomUser, Subject, UserAvailability # นำเข้า Model ที่ต้องการดู

# ลงทะเบียนตาราง Feedback
@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    # กำหนดคอลัมน์ที่จะแสดงในหน้ารวม
    list_display = ('user', 'get_category_display', 'rating', 'created_at')
    # เพิ่มตัวกรองด้านขวามือ (ดูเฉพาะ Bug หรือดูตามดาวที่ให้)
    list_filter = ('category', 'rating', 'created_at')
    # เพิ่มช่องค้นหา (ค้นหาจากชื่อผู้ใช้ หรือเนื้อหา)
    search_fields = ('user__username', 'message')
    # ป้องกันไม่ให้เผลอแก้ไขเวลาที่ส่ง
    readonly_fields = ('created_at',)

# (ทางเลือก) คุณสามารถลงทะเบียน Model อื่นๆ เพื่อเข้าไปดูข้อมูลได้ด้วย เช่น
admin.site.register(CustomUser)
admin.site.register(Subject)
admin.site.register(UserAvailability)