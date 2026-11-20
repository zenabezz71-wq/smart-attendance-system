import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin System"
        CONTROL = "CONTROL", "Control Staff"
        DOCTOR = "DOCTOR", "Doctor / TA"
        STUDENT = "STUDENT", "Student"
        DEVICE_MANAGER = "DEVICE_MANAGER", "Device Manager"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)

    @property
    def display_name(self):
        return self.get_full_name() or self.username


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    student_id = models.CharField(max_length=20, unique=True)
    nfc_tag_id = models.CharField(max_length=32, unique=True, help_text="Card UID, upper-case hex")
    department = models.CharField(max_length=100, blank=True)
    level = models.PositiveSmallIntegerField(default=1)

    def save(self, *args, **kwargs):
        self.nfc_tag_id = self.nfc_tag_id.strip().upper()
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.user.display_name

    def __str__(self):
        return f"{self.student_id} {self.full_name}"


class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="doctor_profile")
    doctor_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100, blank=True)

    @property
    def full_name(self):
        return self.user.display_name

    def __str__(self):
        return f"{self.doctor_id} {self.full_name}"


class Course(models.Model):
    course_code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="courses")
    min_attendance = models.PositiveSmallIntegerField(default=75, help_text="Minimum attendance percent")

    def __str__(self):
        return f"{self.course_code} {self.name}"


class Room(models.Model):
    room_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField(default=30)

    def __str__(self):
        return self.room_id


def new_api_key():
    return secrets.token_urlsafe(24)


class Device(models.Model):
    class Status(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        OFFLINE = "OFFLINE", "Offline"
        DISABLED = "DISABLED", "Disabled"

    device_code = models.CharField(max_length=30, unique=True)
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="devices")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OFFLINE)
    api_key = models.CharField(max_length=64, default=new_api_key)
    last_seen = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.device_code


class Schedule(models.Model):
    DAYS = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
            (4, "Friday"), (5, "Saturday"), (6, "Sunday")]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="schedules")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="schedules")
    day = models.PositiveSmallIntegerField(choices=DAYS)  # Python weekday(): Monday=0
    start_time = models.TimeField()
    end_time = models.TimeField()
    late_after_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="Overrides LATE_AFTER_MINUTES")

    class Meta:
        ordering = ["day", "start_time"]

    def __str__(self):
        return f"{self.course.course_code} {self.get_day_display()} {self.start_time:%H:%M}"


class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")

    class Meta:
        unique_together = ("student", "course")


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        LATE = "LATE", "Late"
        ABSENT = "ABSENT", "Absent"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="attendance")
    schedule = models.ForeignKey(Schedule, on_delete=models.SET_NULL, null=True, blank=True)
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    timestamp = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices)

    class Meta:
        unique_together = ("student", "course", "date")
        ordering = ["-timestamp"]


class Grade(models.Model):
    class Type(models.TextChoices):
        QUIZ = "QUIZ", "Quiz"
        MIDTERM = "MIDTERM", "Midterm"
        ASSIGNMENT = "ASSIGNMENT", "Assignment"
        FINAL = "FINAL", "Final"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="grades")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="grades")
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT)
    grade_type = models.CharField(max_length=12, choices=Type.choices)
    score = models.DecimalField(max_digits=6, decimal_places=2)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100)


class Behavior(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="behaviors")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="behaviors")
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT)
    behavior_points = models.IntegerField(help_text="Positive or negative")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Bonus(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="bonuses")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="bonuses")
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT)
    bonus_score = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditLog(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=60)
    details = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]


def audit(user, action, details=""):
    AuditLog.objects.create(user=user if getattr(user, "pk", None) else None, action=action, details=details[:1000])
