from django.db.models import Q
from rest_framework import viewsets
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import analytics
from . import models as m
from . import serializers as s
from .models import audit
from .permissions import R, RolePermission

ADMIN, CONTROL, DOCTOR, STUDENT, DEVMAN = R.ADMIN, R.CONTROL, R.DOCTOR, R.STUDENT, R.DEVICE_MANAGER
ACADEMIC_ADMINS = {ADMIN, CONTROL}


def doctor_of(user):
    return getattr(user, "doctor_profile", None)


def student_of(user):
    return getattr(user, "student_profile", None)


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [RolePermission]
    read_roles = {ADMIN}
    write_roles = {ADMIN}
    audit_name = ""

    def scope(self, qs, user):
        return qs

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        return qs if u.is_superuser else self.scope(qs, u)

    def _log(self, verb, obj):
        audit(self.request.user, f"{verb}_{self.audit_name or obj.__class__.__name__.upper()}", str(obj.pk))

    def perform_create(self, ser):
        obj = ser.save()
        self._log("CREATE", obj)

    def perform_update(self, ser):
        obj = ser.save()
        self._log("UPDATE", obj)

    def perform_destroy(self, inst):
        self._log("DELETE", inst)
        inst.delete()


class UserViewSet(BaseViewSet):
    queryset = m.User.objects.all().order_by("id")
    serializer_class = s.UserSerializer


class StudentViewSet(BaseViewSet):
    queryset = m.Student.objects.select_related("user").order_by("student_id")
    serializer_class = s.StudentSerializer
    read_roles = {ADMIN, CONTROL, DOCTOR, STUDENT}
    write_roles = ACADEMIC_ADMINS

    def scope(self, qs, u):
        if u.role == DOCTOR:
            return qs.filter(enrollments__course__doctor__user=u).distinct()
        if u.role == STUDENT:
            return qs.filter(user=u)
        return qs if u.role in ACADEMIC_ADMINS else qs.none()


class DoctorViewSet(BaseViewSet):
    queryset = m.Doctor.objects.select_related("user").order_by("doctor_id")
    serializer_class = s.DoctorSerializer
    read_roles = {ADMIN, CONTROL}
    write_roles = {ADMIN}


class CourseViewSet(BaseViewSet):
    queryset = m.Course.objects.all().order_by("course_code")
    serializer_class = s.CourseSerializer
    read_roles = {ADMIN, CONTROL, DOCTOR, STUDENT}
    write_roles = ACADEMIC_ADMINS

    def scope(self, qs, u):
        if u.role == DOCTOR:
            return qs.filter(doctor__user=u)
        if u.role == STUDENT:
            return qs.filter(enrollments__student__user=u)
        return qs if u.role in ACADEMIC_ADMINS else qs.none()


class RoomViewSet(BaseViewSet):
    queryset = m.Room.objects.all().order_by("room_id")
    serializer_class = s.RoomSerializer
    read_roles = {ADMIN, CONTROL, DEVMAN, DOCTOR}
    write_roles = {ADMIN, CONTROL}


class DeviceViewSet(BaseViewSet):
    queryset = m.Device.objects.all().order_by("device_code")
    serializer_class = s.DeviceSerializer
    read_roles = {ADMIN, DEVMAN, CONTROL}
    write_roles = {ADMIN, DEVMAN}

    def get_serializer(self, *a, **kw):
        ser = super().get_serializer(*a, **kw)
        # Hide device secrets from Control Staff (read-only role).
        return ser

    def list(self, request, *a, **kw):
        resp = super().list(request, *a, **kw)
        if request.user.role == CONTROL and not request.user.is_superuser:
            for row in resp.data["results"]:
                row.pop("api_key", None)
        return resp


class ScheduleViewSet(BaseViewSet):
    queryset = m.Schedule.objects.select_related("course", "room").order_by("day", "start_time")
    serializer_class = s.ScheduleSerializer
    read_roles = {ADMIN, CONTROL, DOCTOR, STUDENT, DEVMAN}
    write_roles = ACADEMIC_ADMINS

    def scope(self, qs, u):
        if u.role == DOCTOR:
            return qs.filter(course__doctor__user=u)
        if u.role == STUDENT:
            return qs.filter(course__enrollments__student__user=u)
        return qs


class EnrollmentViewSet(BaseViewSet):
    queryset = m.Enrollment.objects.all().order_by("id")
    serializer_class = s.EnrollmentSerializer
    read_roles = {ADMIN, CONTROL, DOCTOR, STUDENT}
    write_roles = ACADEMIC_ADMINS

    def scope(self, qs, u):
        if u.role == DOCTOR:
            return qs.filter(course__doctor__user=u)
        if u.role == STUDENT:
            return qs.filter(student__user=u)
        return qs if u.role in ACADEMIC_ADMINS else qs.none()


class OwnCourseMixin:
    """Doctor-owned records: doctors may only write for their own courses."""

    def scope(self, qs, u):
        if u.role == DOCTOR:
            return qs.filter(course__doctor__user=u)
        if u.role == STUDENT:
            return qs.filter(student__user=u)
        return qs if u.role in ACADEMIC_ADMINS else qs.none()

    def _check_course(self, ser):
        u = self.request.user
        course = ser.validated_data.get("course") or (ser.instance.course if ser.instance else None)
        if u.role == DOCTOR and course and course.doctor.user_id != u.id:
            raise PermissionDenied("Not your course")
        student = ser.validated_data.get("student")
        if u.role == DOCTOR and student and not m.Enrollment.objects.filter(student=student, course=course).exists():
            raise PermissionDenied("Student is not enrolled in this course")

    def perform_create(self, ser):
        self._check_course(ser)
        u = self.request.user
        doc = doctor_of(u) or ser.validated_data["course"].doctor
        obj = ser.save(**({"doctor": doc} if "doctor" in [f.name for f in ser.Meta.model._meta.fields] else {}))
        self._log("CREATE", obj)

    def perform_update(self, ser):
        self._check_course(ser)
        super().perform_update(ser)


class AttendanceViewSet(OwnCourseMixin, BaseViewSet):
    queryset = m.Attendance.objects.select_related("student__user").order_by("-timestamp")
    serializer_class = s.AttendanceSerializer
    read_roles = {ADMIN, CONTROL, DOCTOR, STUDENT}
    write_roles = {ADMIN, CONTROL, DOCTOR}


class GradeViewSet(OwnCourseMixin, BaseViewSet):
    queryset = m.Grade.objects.all().order_by("-id")
    serializer_class = s.GradeSerializer
    read_roles = {ADMIN, CONTROL, DOCTOR, STUDENT}
    write_roles = {ADMIN, DOCTOR}


class BehaviorViewSet(OwnCourseMixin, BaseViewSet):
    queryset = m.Behavior.objects.all().order_by("-id")
    serializer_class = s.BehaviorSerializer
    read_roles = {ADMIN, CONTROL, DOCTOR, STUDENT}
    write_roles = {ADMIN, DOCTOR}


class BonusViewSet(OwnCourseMixin, BaseViewSet):
    queryset = m.Bonus.objects.all().order_by("-id")
    serializer_class = s.BonusSerializer
    read_roles = {ADMIN, CONTROL, DOCTOR, STUDENT}
    write_roles = {ADMIN, DOCTOR}


class AuditLogViewSet(BaseViewSet):
    queryset = m.AuditLog.objects.all()
    serializer_class = s.AuditLogSerializer
    http_method_names = ["get", "head", "options"]
    read_roles = {ADMIN}


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        from django.contrib.auth import authenticate
        user = authenticate(username=request.data.get("username"), password=request.data.get("password"))
        if not user:
            return Response({"detail": "Invalid credentials"}, status=400)
        token, _ = Token.objects.get_or_create(user=user)
        audit(user, "LOGIN", "api")
        return Response({"token": token.key, "role": user.role, "name": user.display_name})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({"id": u.id, "username": u.username, "name": u.display_name, "role": u.role})


class StudentAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        u = request.user
        student = m.Student.objects.filter(pk=pk).first()
        if not student:
            return Response({"detail": "Not found"}, status=404)
        allowed = (u.is_superuser or u.role in ACADEMIC_ADMINS or
                   (u.role == STUDENT and student.user_id == u.id) or
                   (u.role == DOCTOR and m.Enrollment.objects.filter(student=student, course__doctor__user=u).exists()))
        if not allowed:
            return Response({"detail": "Forbidden"}, status=403)
        rep = analytics.student_report(student)
        if u.role == DOCTOR:  # doctors only see their own courses
            rep["courses"] = [c for c in rep["courses"] if m.Course.objects.filter(pk=c["course_id"], doctor__user=u).exists()]
        rep["recommendations"] = analytics.recommendations(rep)
        return Response(rep)


class CourseAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        u = request.user
        course = m.Course.objects.filter(pk=pk).first()
        if not course:
            return Response({"detail": "Not found"}, status=404)
        if not (u.is_superuser or u.role in ACADEMIC_ADMINS or (u.role == DOCTOR and course.doctor.user_id == u.id)):
            return Response({"detail": "Forbidden"}, status=403)
        return Response(analytics.course_report(course))


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        if not (u.is_superuser or u.role in {ADMIN, CONTROL, DEVMAN}):
            return Response({"detail": "Forbidden"}, status=403)
        from .dashboard_data import control_summary
        return Response(control_summary())
