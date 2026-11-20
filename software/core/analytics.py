"""Analytics engine.

Attendance rate  A = (attended / total sessions) * 100       (PRESENT and LATE count as attended)
Grades           G = mean of (score / max_score) * 100 over the student's grades in the course
Behavior         B = clamp(BEHAVIOR_BASE + sum(behavior_points) + sum(bonus_score), 0, 100)
KPI              = 0.4*A + 0.4*G + 0.2*B
"""
from decimal import Decimal

from .models import Attendance, Behavior, Bonus, Course, Enrollment, Grade, Student

BEHAVIOR_BASE = 70
W_ATT, W_GRADE, W_BEHAVIOR = 0.4, 0.4, 0.2


def risk_level(kpi):
    if kpi < 50:
        return "AT_RISK"
    if kpi < 70:
        return "WARNING"
    return "GOOD"


def attendance_rate(student, course=None):
    qs = Attendance.objects.filter(student=student)
    if course:
        qs = qs.filter(course=course)
    total = qs.count()
    if total == 0:
        return 0.0
    attended = qs.exclude(status=Attendance.Status.ABSENT).count()
    return round(attended / total * 100, 1)


def grade_average(student, course=None):
    qs = Grade.objects.filter(student=student)
    if course:
        qs = qs.filter(course=course)
    pcts = [float(g.score / g.max_score * 100) for g in qs if g.max_score]
    return round(sum(pcts) / len(pcts), 1) if pcts else 0.0


def behavior_score(student, course=None):
    b = Behavior.objects.filter(student=student)
    n = Bonus.objects.filter(student=student)
    if course:
        b, n = b.filter(course=course), n.filter(course=course)
    pts = sum(x.behavior_points for x in b)
    bonus = sum((x.bonus_score for x in n), Decimal(0))
    return round(max(0, min(100, BEHAVIOR_BASE + pts + float(bonus))), 1)


def kpi(student, course=None):
    a, g, b = attendance_rate(student, course), grade_average(student, course), behavior_score(student, course)
    score = round(W_ATT * a + W_GRADE * g + W_BEHAVIOR * b, 1)
    return {"attendance": a, "grades": g, "behavior": b, "kpi": score, "risk": risk_level(score)}


def student_report(student):
    courses = []
    for e in Enrollment.objects.filter(student=student).select_related("course"):
        c = e.course
        data = kpi(student, c)
        data.update({
            "course_id": c.id, "course_code": c.course_code, "course": c.name,
            "min_attendance": c.min_attendance,
            "below_min_attendance": data["attendance"] < c.min_attendance,
        })
        courses.append(data)
    overall = kpi(student)
    return {"student": student.full_name, "student_id": student.student_id, "overall": overall, "courses": courses}


def course_report(course):
    rows = []
    for e in Enrollment.objects.filter(course=course).select_related("student__user"):
        d = kpi(e.student, course)
        d.update({"student_id": e.student.student_id, "student": e.student.full_name})
        rows.append(d)
    avg = round(sum(r["attendance"] for r in rows) / len(rows), 1) if rows else 0.0
    return {"course": course.name, "course_code": course.course_code,
            "average_attendance": avg, "students": rows,
            "at_risk": [r for r in rows if r["risk"] == "AT_RISK"]}


def at_risk_students(limit=10):
    out = []
    for s in Student.objects.select_related("user"):
        d = kpi(s)
        if d["risk"] != "GOOD":
            d.update({"student_id": s.student_id, "student": s.full_name})
            out.append(d)
    out.sort(key=lambda r: r["kpi"])
    return out[:limit]


def recommendations(report):
    tips = []
    for c in report["courses"]:
        if c["below_min_attendance"]:
            tips.append(f"{c['course_code']}: attendance {c['attendance']}% is below the required {c['min_attendance']}%.")
        if c["grades"] and c["grades"] < 60:
            tips.append(f"{c['course_code']}: grades average {c['grades']}%. Ask the doctor for support.")
    if not tips:
        tips.append("Keep it up. Your attendance and grades are on track.")
    return tips
