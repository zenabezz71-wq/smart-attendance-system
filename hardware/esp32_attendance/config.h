#pragma once
// ---------------------------------------------------------------
// Device configuration. Edit these values before flashing.
// ---------------------------------------------------------------

// Wi-Fi (ESP32 supports 2.4 GHz only)
#define WIFI_SSID        "YOUR_WIFI_NAME"
#define WIFI_PASSWORD    "YOUR_WIFI_PASSWORD"

// Backend scan endpoint. Use the PC/server LAN IP, not localhost.
// Example: http://192.168.1.50:8000/api/v1/attendance/scan/
#define SERVER_URL       "http://192.168.1.50:8000/api/v1/attendance/scan/"

// Must match a Device record in the backend (device_code + api_key).
#define DEVICE_ID        "DEV_R101"
#define DEVICE_API_KEY   "DEV_R101_SECRET"

// Time (NTP). Egypt is UTC+2; the backend works in UTC so keep offset 0.
#define NTP_SERVER       "pool.ntp.org"

// Same card is ignored again for this many milliseconds (local debounce).
#define CARD_COOLDOWN_MS 3000

// HTTP timeout in milliseconds.
#define HTTP_TIMEOUT_MS  8000

// I2C address of the LCD backpack. Most boards are 0x27, some are 0x3F.
#define LCD_I2C_ADDRESS  0x27
