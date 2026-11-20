from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views_api as v
from .scan import ScanView

router = DefaultRouter()
router.register("users", v.UserViewSet)
router.register("students", v.StudentViewSet)
router.register("doctors", v.DoctorViewSet)
router.register("courses", v.CourseViewSet)
router.register("rooms", v.RoomViewSet)
router.register("devices", v.DeviceViewSet)
router.register("schedules", v.ScheduleViewSet)
router.register("enrollments", v.EnrollmentViewSet)
router.register("attendance", v.AttendanceViewSet)
router.register("grades", v.GradeViewSet)
router.register("behavior", v.BehaviorViewSet)
router.register("bonus", v.BonusViewSet)
router.register("audit-logs", v.AuditLogViewSet)

urlpatterns = [
    path("attendance/scan/", ScanView.as_view(), name="scan"),   # must come before the router's attendance/<pk>/
    path("auth/login/", v.LoginView.as_view()),
    path("auth/me/", v.MeView.as_view()),
    path("analytics/students/<int:pk>/", v.StudentAnalyticsView.as_view()),
    path("analytics/courses/<int:pk>/", v.CourseAnalyticsView.as_view()),
    path("analytics/dashboard/", v.DashboardSummaryView.as_view()),
    path("", include(router.urls)),
]
