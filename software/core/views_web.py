from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import analytics
from . import models as m
from .dashboard_data import control_summary
from .models import audit

R = m.User.Role


def home(request):
    return redirect("dashboard" if request.user.is_authenticated else "login")


@login_required
def dashboard(request):
    role = request.user.role
    if request.user.is_superuser or role in (R.ADMIN, R.CONTROL, R.DEVICE_MANAGER):
        return control(request)
    if role == R.DOCTOR:
        return doctor(request)
    return student(request)


def control(request):
    data = control_summary()
    data["role"] = request.user.get_role_display()
    data["courses"] = [analytics.course_report(c) for c in m.Course.objects.all()]
    data["can_manage_devices"] = request.user.role in (R.ADMIN, R.DEVICE_MANAGER) or request.user.is_superuser
    data["audit"] = m.AuditLog.objects.select_related("user")[:8] if (request.user.role == R.ADMIN or request.user.is_superuser) else []
    return render(request, "core/control.html", data)


def doctor(request):
    doc = getattr(request.user, "doctor_profile", None)
    if not doc:
        raise Http404("No doctor profile")
    courses = list(m.Course.objects.filter(doctor=doc))
    return render(request, "core/doctor.html", {
        "doctor": doc,
        "reports": [analytics.course_report(c) for c in courses],
        "courses": courses,
        "enrollments": m.Enrollment.objects.filter(course__in=courses).select_related("student__user", "course"),
        "grade_types": m.Grade.Type.choices,
    })


def student(request):
    st = getattr(request.user, "student_profile", None)
    if not st:
        raise Http404("No student profile")
    rep = analytics.student_report(st)
    return render(request, "core/student.html", {
        "report": rep,
        "tips": analytics.recommendations(rep),
        "attendance": m.Attendance.objects.filter(student=st).select_related("course")[:15],
        "grades": m.Grade.objects.filter(student=st).select_related("course"),
        "behaviors": m.Behavior.objects.filter(student=st).select_related("course")[:10],
    })


@login_required
@require_POST
def doctor_record(request):
    """Doctor portal form: add grade / behavior points / bonus for a student in their own course."""
    doc = getattr(request.user, "doctor_profile", None)
    if not doc:
        raise Http404()
    try:
        enr = m.Enrollment.objects.select_related("student", "course").get(pk=request.POST["enrollment"], course__doctor=doc)
        kind = request.POST["kind"]
        if kind == "grade":
            m.Grade.objects.create(student=enr.student, course=enr.course, doctor=doc,
                                   grade_type=request.POST["grade_type"], score=request.POST["value"],
                                   max_score=request.POST.get("max_score") or 100)
        elif kind == "behavior":
            m.Behavior.objects.create(student=enr.student, course=enr.course, doctor=doc,
                                      behavior_points=int(request.POST["value"]), notes=request.POST.get("note", ""))
        elif kind == "bonus":
            m.Bonus.objects.create(student=enr.student, course=enr.course, doctor=doc,
                                   bonus_score=request.POST["value"], reason=request.POST.get("note", ""))
        else:
            raise ValueError("kind")
        audit(request.user, f"DOCTOR_ADD_{kind.upper()}", f"student={enr.student.student_id} course={enr.course.course_code}")
        messages.success(request, "Saved")
    except Exception:
        messages.error(request, "Could not save. Check the values.")
    return redirect("dashboard")


def simulator(request):
    path = Path(settings.BASE_DIR).parent / "hardware" / "simulator" / "index.html"
    if not path.exists():
        raise Http404("Simulator file not found")
    return HttpResponse(path.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")


def demo(request):
    """Committee presentation page: device simulator, student portal and control dashboard in one screen.

    Public on purpose: it is a read-only demo view over the seeded demo data, so the committee
    does not need to sign in as three roles at once. The individual role portals stay login-gated.
    """
    return render(request, "core/demo.html")


def demo_state(request):
    """JSON snapshot the demo page polls: the same control summary and per-student reports."""
    students = []
    for s in m.Student.objects.select_related("user").order_by("student_id"):
        rep = analytics.student_report(s)
        students.append({
            "id": s.student_id,
            "name": s.full_name,
            "overall": rep["overall"],
            "courses": rep["courses"],
            "sheet": [{"date": str(a.date), "course": a.course.course_code, "status": a.status,
                       "time": a.timestamp}
                      for a in m.Attendance.objects.filter(student=s).select_related("course")[:8]],
        })
    return JsonResponse({"control": control_summary(), "students": students}, encoder=DjangoJSONEncoder)
