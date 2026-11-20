from datetime import datetime, time, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core import analytics
from core.models import Attendance, Behavior, Course, Device, Schedule, Student, User


def scan(client, uid="A1B2C3D4", device="DEV_R101", key="DEV_R101_SECRET", ts=None):
    body = {"device_id": device, "card_uid": uid}
    if ts:
        body["timestamp"] = ts.isoformat()
    return client.post("/api/v1/attendance/scan/", body, format="json", HTTP_X_DEVICE_KEY=key)


class SeededCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def login(self, username):
        c = APIClient()
        tok = c.post("/api/v1/auth/login/", {"username": username, "password": "demo12345"}, format="json").data["token"]
        c.credentials(HTTP_AUTHORIZATION=f"Token {tok}")
        return c


class ScanTests(SeededCase):
    def test_contract_success(self):
        Attendance.objects.all().delete()
        r = scan(APIClient())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data), {"success", "status", "student", "course"})
        self.assertTrue(r.data["success"])
        self.assertEqual(r.data["student"], "Ahmed Mohamed")
        self.assertEqual(r.data["course"], "Database Systems")

    def test_duplicate_blocked(self):
        Attendance.objects.all().delete()
        scan(APIClient())
        r = scan(APIClient())
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["status"], "DUPLICATE")

    def test_unknown_card_and_bad_key(self):
        self.assertEqual(scan(APIClient(), uid="00000000").status_code, 404)
        self.assertEqual(scan(APIClient(), key="wrong").status_code, 401)
        self.assertEqual(scan(APIClient(), device="NOPE").status_code, 401)

    def test_late_status(self):
        Attendance.objects.all().delete()
        Schedule.objects.all().delete()
        course = Course.objects.get(course_code="BIS301")
        room = Device.objects.get(device_code="DEV_R101").room
        now = timezone.localtime()
        start = (now - timedelta(minutes=30)).time()
        Schedule.objects.create(course=course, room=room, day=now.weekday(), start_time=start, end_time=time(23, 59))
        if start > now.time():
            self.skipTest("crossed midnight")
        r = scan(APIClient())
        self.assertEqual(r.data["status"], "LATE")

    def test_no_session(self):
        Schedule.objects.all().delete()
        self.assertEqual(scan(APIClient()).data["status"], "NO_SESSION")

    def test_disabled_device(self):
        Device.objects.filter(device_code="DEV_R101").update(status="DISABLED")
        self.assertEqual(scan(APIClient()).status_code, 403)


class AnalyticsTests(SeededCase):
    def test_kpi_formula(self):
        s = Student.objects.get(student_id="S1001")
        d = analytics.kpi(s)
        self.assertAlmostEqual(d["kpi"], round(0.4 * d["attendance"] + 0.4 * d["grades"] + 0.2 * d["behavior"], 1), places=1)

    def test_attendance_rate(self):
        s = Student.objects.get(student_id="S1001")
        c = Course.objects.get(course_code="BIS301")
        Attendance.objects.filter(student=s, course=c).delete()
        today = timezone.localdate()
        for i, st in enumerate(["PRESENT", "PRESENT", "LATE", "ABSENT"]):
            Attendance.objects.create(student=s, course=c, date=today - timedelta(days=i + 1),
                                      timestamp=timezone.now(), status=st)
        self.assertEqual(analytics.attendance_rate(s, c), 75.0)

    def test_weak_student_is_flagged(self):
        s = Student.objects.get(student_id="S1006")
        self.assertIn(analytics.kpi(s)["risk"], ("AT_RISK", "WARNING"))


class RbacTests(SeededCase):
    def test_student_sees_only_self(self):
        c = self.login("s1001")
        self.assertEqual(c.get("/api/v1/students/").data["count"], 1)
        self.assertEqual(c.get("/api/v1/devices/").status_code, 403)
        other = Student.objects.get(student_id="S1002")
        self.assertEqual(c.get(f"/api/v1/analytics/students/{other.id}/").status_code, 403)

    def test_student_cannot_write(self):
        c = self.login("s1001")
        self.assertEqual(c.post("/api/v1/grades/", {}, format="json").status_code, 403)

    def test_doctor_scope(self):
        c = self.login("dr_laila")
        codes = {x["course_code"] for x in c.get("/api/v1/courses/").data["results"]}
        self.assertEqual(codes, {"BIS310"})
        other = Course.objects.get(course_code="BIS301")
        self.assertEqual(c.get(f"/api/v1/analytics/courses/{other.id}/").status_code, 403)

    def test_doctor_adds_behavior_for_own_course_only(self):
        c = self.login("dr_laila")
        s = Student.objects.get(student_id="S1001")
        own = Course.objects.get(course_code="BIS310")
        foreign = Course.objects.get(course_code="BIS301")
        ok = c.post("/api/v1/behavior/", {"student": s.id, "course": own.id, "behavior_points": 2}, format="json")
        self.assertEqual(ok.status_code, 201)
        bad = c.post("/api/v1/behavior/", {"student": s.id, "course": foreign.id, "behavior_points": 2}, format="json")
        self.assertEqual(bad.status_code, 403)

    def test_device_manager_and_control(self):
        self.assertEqual(self.login("devmanager").get("/api/v1/devices/").status_code, 200)
        self.assertEqual(self.login("devmanager").get("/api/v1/students/").status_code, 403)
        ctl = self.login("control")
        self.assertEqual(ctl.get("/api/v1/students/").data["count"], 6)
        self.assertEqual(ctl.post("/api/v1/devices/", {}, format="json").status_code, 403)
        self.assertNotIn("api_key", ctl.get("/api/v1/devices/").data["results"][0])

    def test_audit_admin_only(self):
        self.assertEqual(self.login("control").get("/api/v1/audit-logs/").status_code, 403)
        self.assertEqual(self.login("admin").get("/api/v1/audit-logs/").status_code, 200)

    def test_requires_auth(self):
        self.assertEqual(APIClient().get("/api/v1/students/").status_code, 401)


class WebTests(SeededCase):
    def test_dashboards_render_per_role(self):
        from django.test import Client
        for username, needle in [("control", "Control Dashboard"), ("dr_hany", "Doctor Portal"),
                                 ("s1001", "Student Portal"), ("devmanager", "Control Dashboard")]:
            c = Client()
            self.assertTrue(c.login(username=username, password="demo12345"))
            r = c.get("/dashboard/")
            self.assertContains(r, needle)

    def test_doctor_form(self):
        from django.test import Client
        from core.models import Enrollment
        c = Client()
        c.login(username="dr_hany", password="demo12345")
        enr = Enrollment.objects.filter(course__course_code="BIS301").first()
        c.post("/dashboard/record/", {"enrollment": enr.id, "kind": "behavior", "value": "5", "note": "x"})
        self.assertTrue(Behavior.objects.filter(student=enr.student, behavior_points=5).exists())


class DemoPageTests(SeededCase):
    def test_demo_page_public(self):
        r = self.client.get("/demo/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Control dashboard")

    def test_demo_state_public(self):
        r = self.client.get("/demo/state/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("control", data)
        self.assertIn("students", data)
        self.assertEqual(len(data["students"]), 6)
        self.assertIn("overall", data["students"][0])

    def test_demo_state_reflects_scan(self):
        Attendance.objects.all().delete()
        self.assertEqual(scan(APIClient()).status_code, 200)
        data = self.client.get("/demo/state/").json()
        self.assertEqual(data["control"]["recent"][0]["student"], "Ahmed Mohamed")
        sheet = data["students"][0]["sheet"]
        self.assertEqual(sheet[0]["status"], "PRESENT")

    def test_simulator_frameable_same_origin(self):
        r = self.client.get("/simulator/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("X-Frame-Options"), "SAMEORIGIN")
