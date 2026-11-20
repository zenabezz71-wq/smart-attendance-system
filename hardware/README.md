# Hardware: ESP32 attendance reader

Firmware for one classroom reader. A student taps a card, the ESP32 sends the card UID to the Django backend, and the LCD, LEDs and buzzer show the result.

## Parts

| Part | Notes |
|---|---|
| ESP32 DevKit V1 | Wi-Fi built in |
| RC522 RFID reader (13.56 MHz) | Runs on **3.3 V only**. 5 V will damage it |
| LCD 16x2 with I2C backpack | Address 0x27 (some are 0x3F) |
| Green LED, red LED | One resistor each, 220 to 330 ohm |
| Buzzer (active) | Direct on the GPIO is fine for a small active buzzer |
| MIFARE cards or tags | UID is what the backend matches (`nfc_tag_id`) |

## Wiring (pin map from the spec)

| Module pin | ESP32 GPIO |
|---|---|
| RC522 SCK | 18 |
| RC522 MISO | 19 |
| RC522 MOSI | 23 |
| RC522 SDA (SS) | 5 |
| RC522 RST | 4 (the spec does not list RST; use GPIO 4 or tie RST to 3.3 V and change `RC522_RST` to `-1`) |
| RC522 3.3V / GND | 3V3 / GND |
| LCD SDA | 21 |
| LCD SCL | 22 |
| LCD VCC / GND | 5V (VIN) / GND (most I2C LCD backpacks need 5 V) |
| Green LED (+ resistor) | 25 |
| Red LED (+ resistor) | 26 |
| Buzzer | 27 |

LED wiring: GPIO -> resistor -> LED anode, LED cathode -> GND.

## Flash it

1. Install Arduino IDE 2.x and add the ESP32 boards package (Boards Manager, "esp32 by Espressif").
2. Install libraries: `MFRC522`, `LiquidCrystal I2C`, `ArduinoJson`.
3. Open `esp32_attendance/esp32_attendance.ino`.
4. Edit `config.h`: Wi-Fi name and password, `SERVER_URL` (your server LAN IP), `DEVICE_ID`, `DEVICE_API_KEY`.
5. Board: "DOIT ESP32 DEVKIT V1". Select the COM port and upload. Serial monitor at 115200.

## Backend pairing

The `DEVICE_ID` and `DEVICE_API_KEY` must match a Device in the backend. With the demo data (`python manage.py seed_demo`) the values already in `config.h` work: `DEV_R101` / `DEV_R101_SECRET`.

The firmware sends:

```
POST /api/v1/attendance/scan/
X-Device-Key: <DEVICE_API_KEY>
{"device_id": "DEV_R101", "card_uid": "A1B2C3D4", "timestamp": "2026-11-11T09:15:00Z"}
```

Expected answer: `200 {"success": true, "status": "PRESENT", "student": "...", "course": "..."}`. Any other answer shows the status on the LCD with the red LED and a double beep.

## Behavior

- Boot: indicator self-test, Wi-Fi connect, NTP time sync, "Tap your card".
- Success: student name and status on the LCD, green LED, one short beep.
- Failure (unknown card, no class now, duplicate, server down): red LED, two beeps, reason on the LCD.
- Same card within 3 seconds is ignored locally. The server also blocks duplicates for the same session.
- Timestamp is UTC from NTP. If NTP is not ready the field is left out and the server uses its own time.

## Testing without the hardware

You can test the same request with curl against the backend (see `software/README.md`). The firmware itself needs a real ESP32 and RC522 to test; it was not compiled or run on a board by the author of this repo's generator, so expect to check the LCD address and your RC522 module on first power up.

## Troubleshooting

- LCD blank: adjust the contrast screw on the backpack, try address 0x3F.
- "Card" never reads: check 3.3 V power and the SDA/SS wire on GPIO 5.
- HTTP error or no response: the server must listen on `0.0.0.0:8000` and your firewall must allow it. `ALLOWED_HOSTS` must include the server IP.
