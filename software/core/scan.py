"""Scan endpoint: POST /api/v1/attendance/scan/ (called by the ESP32 reader)."""
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status as http
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Attendance, Device, Enrollment, Schedule, Student, audit
from .serializers import ScanSerializer


def fail(code, status_code, message):
    return Response({"success": False, "status": code, "message": message}, status=status_code)


def find_schedule(room, course_ids, local_dt):
    """Session running in this room at this moment (early window included)."""
    early = timedelta(minutes=settings.EARLY_SCAN_MINUTES)
    for sch in Schedule.objects.filter(room=room, day=local_dt.weekday(), course_id__in=course_ids).select_related("course"):
        start = timezone.make_aware(datetime.combine(local_dt.date(), sch.start_time), local_dt.tzinfo)
        end = timezone.make_aware(datetime.combine(local_dt.date(), sch.end_time), local_dt.tzinfo)
        if start - early <= local_dt <= end:
            return sch, start
    return None, None


class ScanView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        ser = ScanSerializer(data=request.data)
        if not ser.is_valid():
            return fail("BAD_REQUEST", http.HTTP_400_BAD_REQUEST, "device_id and card_uid are required")
        data = ser.validated_data

        device = Device.objects.filter(device_code=data["device_id"]).select_related("room").first()
        key = request.headers.get("X-Device-Key", "")
        if not device or not secrets.compare_digest(device.api_key, key):
            return fail("UNAUTHORIZED_DEVICE", http.HTTP_401_UNAUTHORIZED, "Unknown device or bad key")
        if device.status == Device.Status.DISABLED:
            return fail("DEVICE_DISABLED", http.HTTP_403_FORBIDDEN, "Device is disabled")

        now = timezone.now()
        device.last_seen = now
        device.status = Device.Status.ONLINE
        device.save(update_fields=["last_seen", "status"])

        student = Student.objects.filter(nfc_tag_id=data["card_uid"].strip().upper()).select_related("user").first()
        if not student:
            audit(None, "SCAN_UNKNOWN_CARD", f"{device.device_code} {data['card_uid']}")
            return fail("UNKNOWN_CARD", http.HTTP_404_NOT_FOUND, "Card not registered")

        ts = data.get("timestamp") or now
        local = timezone.localtime(ts)
        course_ids = list(Enrollment.objects.filter(student=student).values_list("course_id", flat=True))
        schedule, start = find_schedule(device.room, course_ids, local)
        if not schedule:
            return fail("NO_SESSION", http.HTTP_404_NOT_FOUND, "No class for you in this room now")

        grace = schedule.late_after_minutes if schedule.late_after_minutes is not None else settings.LATE_AFTER_MINUTES
        late_limit = start + timedelta(minutes=grace)
        st = Attendance.Status.LATE if local > late_limit else Attendance.Status.PRESENT
        try:
            with transaction.atomic():
                Attendance.objects.create(
                    student=student, course=schedule.course, schedule=schedule, device=device,
                    date=local.date(), timestamp=ts, status=st)
        except IntegrityError:
            return fail("DUPLICATE", http.HTTP_409_CONFLICT, "Already registered today")

        audit(None, "SCAN_OK", f"{device.device_code} {student.student_id} {schedule.course.course_code} {st}")
        return Response({"success": True, "status": st, "student": student.full_name,
                         "course": schedule.course.name}, status=http.HTTP_200_OK)
