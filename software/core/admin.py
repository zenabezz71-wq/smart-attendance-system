from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from . import models

admin.site.register(models.User, UserAdmin)
for m in (models.Student, models.Doctor, models.Course, models.Room, models.Device, models.Schedule,
          models.Enrollment, models.Attendance, models.Grade, models.Behavior, models.Bonus, models.AuditLog):
    admin.site.register(m)
