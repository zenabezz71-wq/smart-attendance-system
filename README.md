# Smart Academic Attendance & Student Performance Management System

BIS graduation project. An ESP32 + RFID reader registers student attendance in a Django REST backend, which feeds analytics and dashboards.

```
hardware/
  esp32_attendance/   ESP32 firmware (Arduino): RC522, LCD, LEDs, buzzer, HTTP POST
  simulator/          Browser maquette of the device (LCD, LEDs, buzzer, card tap)
  README.md           Parts list, wiring, flashing
software/
  config/             Django settings and URLs
  core/               Models (13 tables + auth), REST API, scan endpoint, analytics, dashboards, seed, tests
  README.md           Setup, API, roles, formulas
render.yaml           Render blueprint (free demo web service, SQLite)
docker-compose.yml    Local PostgreSQL + backend
```

## Quick start (no hardware needed)

```bash
cd software
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open http://127.0.0.1:8000/ and log in (demo password `demo12345`, users `admin`, `control`, `devmanager`, `dr_hany`, `dr_laila`, `s1001`). Open http://127.0.0.1:8000/simulator/ to tap virtual cards.

## How the parts connect

`card tap -> ESP32 -> POST /api/v1/attendance/scan/ -> Django (match card, room, schedule) -> Attendance row -> dashboards`

The browser simulator sends the exact same request as the firmware, so the full flow can be demonstrated without a board.

See `hardware/README.md` and `software/README.md` for details.
