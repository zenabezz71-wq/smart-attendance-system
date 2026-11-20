from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from . import analytics
from .models import Attendance, Device, Student


def control_summary():
    today = timezone.localdate()
    today_qs = Attendance.objects.filter(date=today)
    attended = today_qs.exclude(status=Attendance.Status.ABSENT).count()
    total = today_qs.count()
    cutoff = timezone.now() - timedelta(seconds=settings.DEVICE_ONLINE_SECONDS)
    devices = []
    for d in Device.objects.select_related("room").order_by("device_code"):
        online = bool(d.last_seen and d.last_seen >= cutoff and d.status != Device.Status.DISABLED)
        devices.append({"device": d.device_code, "room": d.room.room_id, "online": online,
                        "status": d.status, "last_seen": d.last_seen})
    return {
        "date": today,
        "students": Student.objects.count(),
        "today_scans": total,
        "today_attendance_rate": round(attended / total * 100, 1) if total else 0.0,
        "devices": devices,
        "at_risk": analytics.at_risk_students(),
        "recent": [{"student": a.student.full_name, "course": a.course.course_code, "status": a.status,
                    "time": a.timestamp} for a in Attendance.objects.select_related("student__user", "course")[:10]],
    }
