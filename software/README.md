# Software: Django REST backend, analytics, dashboards

Python 3.10+, Django 5, Django REST Framework. PostgreSQL in production, SQLite for a quick local run.

## Run locally

```bash
cd software
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # demo users, courses, history, devices
python manage.py runserver 0.0.0.0:8000
python manage.py test               # 18 tests
```

### PostgreSQL

Set `DATABASE_URL=postgres://user:pass@host:5432/db`, or `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`. Without them it uses SQLite. `docker compose up` in the repo root starts PostgreSQL and the app.

### Environment

| Variable | Meaning | Default |
|---|---|---|
| `SECRET_KEY` | Django secret. **Set it in production** | dev key |
| `DEBUG` | `1` or `0` | `1` |
| `ALLOWED_HOSTS` | comma list | `*` |
| `LATE_AFTER_MINUTES` | minutes after start that count as LATE | 15 |
| `EARLY_SCAN_MINUTES` | scans accepted this early before start | 15 |

## Demo logins (password `demo12345`)

| Username | Role |
|---|---|
| admin | Admin System |
| control | Control Staff |
| devmanager | Device Manager |
| dr_hany, dr_laila | Doctor / TA |
| s1001 ... s1006 | Student |

Demo cards: s1001 `A1B2C3D4`, s1002 `B2C3D4E5`, s1003 `C3D4E5F6`, s1004 `D4E5F6A7`, s1005 `E5F6A7B8`, s1006 `F6A7B8C9`. Device `DEV_R101` key `DEV_R101_SECRET`.

`seed_demo` also adds a session for Database Systems in room R101 that is open all day, every day, so demos work at any hour. Use `--no-open-session` for a real timetable only. **Change all demo passwords and device keys before any real use.**

## Database (13 tables + Django auth)

`User` (role), `Student` (student_id, nfc_tag_id), `Doctor` (doctor_id, department), `Course` (course_code, min_attendance), `Room` (room_id, capacity), `Device` (device_code, room, status, api_key), `Schedule` (day, start_time, end_time, room), `Enrollment`, `Attendance` (timestamp, status, FKs; unique per student, course, day), `Grade` (grade_type, score, doctor), `Behavior` (behavior_points, notes), `Bonus` (bonus_score, reason), `AuditLog` (action, user, timestamp).

## Scan endpoint (hardware contract)

```
POST /api/v1/attendance/scan/
X-Device-Key: <device api key>
{"device_id": "DEV_R101", "card_uid": "A1B2C3D4", "timestamp": "2026-11-11T09:15:00Z"}

200 {"success": true, "status": "PRESENT", "student": "Ahmed Mohamed", "course": "Database Systems"}
```

Logic: authenticate device by key, find student by card, convert timestamp to Cairo time, find a session in the device's room for a course the student is enrolled in (15 min early window), then PRESENT, or LATE after the grace period. Errors return `{"success": false, "status": CODE, "message": ...}`: `UNAUTHORIZED_DEVICE` 401, `DEVICE_DISABLED` 403, `UNKNOWN_CARD` 404, `NO_SESSION` 404, `DUPLICATE` 409 (already registered that day), `BAD_REQUEST` 400. The `timestamp` field is optional; the server clock is used if omitted.

Try it:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/attendance/scan/ -H "Content-Type: application/json" \
  -H "X-Device-Key: DEV_R101_SECRET" -d '{"device_id":"DEV_R101","card_uid":"A1B2C3D4"}'
```

## REST API

Login: `POST /api/v1/auth/login/` with `{"username","password"}` returns a token; send `Authorization: Token <token>`. Resources under `/api/v1/`: `users`, `students`, `doctors`, `courses`, `rooms`, `devices`, `schedules`, `enrollments`, `attendance`, `grades`, `behavior`, `bonus`, `audit-logs`. Analytics: `analytics/students/<id>/`, `analytics/courses/<id>/`, `analytics/dashboard/`.

## Roles (RBAC)

| Role | Access |
|---|---|
| Admin | Everything, including users and the audit log |
| Control Staff | Students, courses, schedules, enrollments (write); attendance and reports (read and correct); devices read-only without keys |
| Doctor / TA | Own courses only: attendance, grades, behavior, bonus, reports |
| Student | Own data only: attendance, grades, KPI |
| Device Manager | Devices (write), rooms and schedules (read) |

Doctors cannot write for another doctor's course or for a student not enrolled in it. Every create, update, delete, login and scan is written to the audit log.

## Analytics

- Attendance rate `A = attended / total sessions x 100`. PRESENT and LATE count as attended.
- Grades `G` = average of `score / max_score x 100`.
- Behavior `B = clamp(70 + behavior points + bonus, 0, 100)`. The base of 70 is a project assumption, change `BEHAVIOR_BASE` in `core/analytics.py`.
- **KPI = 0.4 A + 0.4 G + 0.2 B.** Risk: below 50 AT_RISK, below 70 WARNING, else GOOD.

Absent rows are created by the seed data and by manual correction. A scheduled "close session" job that marks no-shows ABSENT is not included.

## Dashboards

`/dashboard/` shows the page for the logged-in role: Control dashboard (devices online, live scans, daily rate, at-risk students, per-course tables, audit log), Doctor portal (course reports plus a form to record grades, behavior points and bonus), Student portal (attendance, grades, KPI, recommendations).

## Deploy

`render.yaml` defines a Render web service and a PostgreSQL database. The build runs migrations; set `SEED_DEMO=1` on the first deploy to load demo data. The simulator is a single static file at `hardware/simulator/index.html`, also served at `/simulator/`.

## Known limits

No password reset or email flows. Static device keys, no rate limiting. The firmware has not been run on real hardware by the generator of this repo.
