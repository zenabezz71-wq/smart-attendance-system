import random
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (Attendance, Behavior, Bonus, Course, Device, Doctor, Enrollment, Grade, Room,
                         Schedule, Student, User)

PASSWORD = "demo12345"
STUDENTS = [
    ("s1001", "Ahmed", "Mohamed", "A1B2C3D4"),
    ("s1002", "Sara", "Hassan", "B2C3D4E5"),
    ("s1003", "Omar", "Khaled", "C3D4E5F6"),
    ("s1004", "Mariam", "Ali", "D4E5F6A7"),
    ("s1005", "Youssef", "Adel", "E5F6A7B8"),
    ("s1006", "Nour", "Ibrahim", "F6A7B8C9"),
]


def user(username, role, first, last, **extra):
    u, _ = User.objects.get_or_create(username=username, defaults={"role": role, "first_name": first, "last_name": last, **extra})
    u.role, u.first_name, u.last_name = role, first, last
    u.set_password(PASSWORD)
    u.save()
    return u


class Command(BaseCommand):
    help = "Create demo users, courses, devices, history and an all-week open session for demos."

    def add_arguments(self, parser):
        parser.add_argument("--no-open-session", action="store_true",
                            help="Do not add the demo session that is open every day 00:00-23:59 in R101")

    def handle(self, *args, **opts):
        random.seed(7)
        user("admin", User.Role.ADMIN, "System", "Admin", is_staff=True, is_superuser=True)
        user("control", User.Role.CONTROL, "Mona", "Control")
        user("devmanager", User.Role.DEVICE_MANAGER, "Tarek", "Devices")
        d1 = Doctor.objects.get_or_create(doctor_id="D01", defaults={"user": user("dr_hany", User.Role.DOCTOR, "Hany", "Samir"), "department": "BIS"})[0]
        d2 = Doctor.objects.get_or_create(doctor_id="D02", defaults={"user": user("dr_laila", User.Role.DOCTOR, "Laila", "Fouad"), "department": "BIS"})[0]

        r101 = Room.objects.get_or_create(room_id="R101", defaults={"name": "Lab 101", "capacity": 40})[0]
        r102 = Room.objects.get_or_create(room_id="R102", defaults={"name": "Hall 102", "capacity": 80})[0]
        Device.objects.update_or_create(device_code="DEV_R101", defaults={"room": r101, "api_key": "DEV_R101_SECRET"})
        Device.objects.update_or_create(device_code="DEV_R102", defaults={"room": r102, "api_key": "DEV_R102_SECRET"})

        c1 = Course.objects.get_or_create(course_code="BIS301", defaults={"name": "Database Systems", "doctor": d1, "min_attendance": 75})[0]
        c2 = Course.objects.get_or_create(course_code="BIS305", defaults={"name": "Business Analytics", "doctor": d1, "min_attendance": 75})[0]
        c3 = Course.objects.get_or_create(course_code="BIS310", defaults={"name": "Information Systems Security", "doctor": d2, "min_attendance": 70})[0]

        # Weekly timetable (Sun-Thu)
        for course, room, days, st, en in [(c1, r101, (6, 1), time(9, 0), time(11, 0)),
                                           (c2, r102, (0, 2), time(11, 30), time(13, 30)),
                                           (c3, r102, (3,), time(9, 0), time(11, 0))]:
            for d in days:
                Schedule.objects.get_or_create(course=course, room=room, day=d, start_time=st, end_time=en)
        if not opts["no_open_session"]:
            for d in range(7):  # demo session so the simulator works at any time
                Schedule.objects.get_or_create(course=c1, room=r101, day=d, start_time=time(0, 0), end_time=time(23, 59),
                                               defaults={"late_after_minutes": 24 * 60})

        students = []
        for sid, first, last, uid in STUDENTS:
            u = user(sid, User.Role.STUDENT, first, last)
            s, _ = Student.objects.get_or_create(student_id=sid.upper(), defaults={"user": u, "nfc_tag_id": uid, "department": "BIS", "level": 3})
            students.append(s)
            for c in (c1, c2, c3):
                Enrollment.objects.get_or_create(student=s, course=c)

        # History: 8 past sessions per course. The first student is strong, the last is weak.
        if not Attendance.objects.exists():
            profile = [0.97, 0.9, 0.8, 0.7, 0.55, 0.35]
            today = timezone.localdate()
            for ci, c in enumerate((c1, c2, c3)):
                for k in range(1, 9):
                    day = today - timedelta(days=7 * k + ci + 1)
                    ts = timezone.make_aware(datetime.combine(day, time(9, 5)))
                    for s, p in zip(students, profile):
                        r = random.random()
                        status = "ABSENT" if r > p else ("LATE" if r > p - 0.1 else "PRESENT")
                        Attendance.objects.create(student=s, course=c, date=day, timestamp=ts, status=status)
            grade_base = [92, 84, 76, 68, 55, 40]
            for s, base in zip(students, grade_base):
                for c in (c1, c2, c3):
                    doc = c.doctor
                    for gt, mx in (("QUIZ", 10), ("MIDTERM", 30)):
                        Grade.objects.create(student=s, course=c, doctor=doc, grade_type=gt, max_score=mx,
                                             score=round(mx * min(1, max(0, (base + random.randint(-6, 6)) / 100)), 1))
            for s, pts in zip(students, (6, 3, 0, -4, -9, -15)):
                Behavior.objects.create(student=s, course=c1, doctor=d1, behavior_points=pts, notes="Demo behavior record")
            Bonus.objects.create(student=students[0], course=c1, doctor=d1, bonus_score=3, reason="Excellent participation")

        self.stdout.write(self.style.SUCCESS(
            f"Seeded. Password for every demo user: {PASSWORD}. Logins: admin, control, devmanager, dr_hany, dr_laila, s1001..s1006."))
