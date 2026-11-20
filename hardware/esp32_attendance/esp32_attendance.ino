/*
  Smart Academic Attendance - ESP32 reader firmware
  Board : ESP32 DevKit V1
  Parts : RC522 RFID (13.56 MHz), LCD 16x2 I2C, green LED, red LED, buzzer

  Flow: tap card -> read UID -> POST JSON to the backend -> show result on
  LCD, green LED + short beep on success, red LED + long beep on failure.

  Libraries (Arduino Library Manager):
    - MFRC522            by GithubCommunity (miguelbalboa)
    - LiquidCrystal I2C  by Frank de Brabander
    - ArduinoJson        by Benoit Blanchon (v6 or v7)
*/

#include <SPI.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <MFRC522.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h>
#include <time.h>
#include "config.h"

// ---------------- Pin mapping (from the project specification) ----------------
#define RC522_SCK   18
#define RC522_MISO  19
#define RC522_MOSI  23
#define RC522_SDA   5     // SS / SDA (chip select)
#define RC522_RST   4     // not in the spec table; any free GPIO. Or wire RST to 3.3V and ignore.
#define LCD_SDA     21
#define LCD_SCL     22
#define LED_GREEN   25
#define LED_RED     26
#define BUZZER_PIN  27

MFRC522 rfid(RC522_SDA, RC522_RST);
LiquidCrystal_I2C lcd(LCD_I2C_ADDRESS, 16, 2);

String lastUid = "";
unsigned long lastScanAt = 0;

// ---------------- Helpers ----------------
void showLcd(const String &line1, const String &line2 = "") {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(line1.substring(0, 16));
  lcd.setCursor(0, 1);
  lcd.print(line2.substring(0, 16));
}

void beep(unsigned int ms) {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(ms);
  digitalWrite(BUZZER_PIN, LOW);
}

void signalSuccess() {
  digitalWrite(LED_GREEN, HIGH);
  beep(150);
  delay(350);
  digitalWrite(LED_GREEN, LOW);
}

void signalFailure() {
  digitalWrite(LED_RED, HIGH);
  beep(300); delay(100); beep(300);
  delay(300);
  digitalWrite(LED_RED, LOW);
}

void showReady() {
  showLcd("Smart Attendance", WiFi.status() == WL_CONNECTED ? "Tap your card" : "WiFi offline...");
}

void connectWifi() {
  showLcd("Connecting WiFi", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(300);
  }
  if (WiFi.status() == WL_CONNECTED) {
    showLcd("WiFi connected", WiFi.localIP().toString());
    delay(1000);
  } else {
    showLcd("WiFi failed", "will retry...");
    signalFailure();
  }
}

void syncTime() {
  configTime(0, 0, NTP_SERVER);   // UTC; the server converts to local time
  struct tm t;
  for (int i = 0; i < 20; i++) {
    if (getLocalTime(&t, 500)) return;
  }
}

// ISO-8601 UTC timestamp, e.g. 2026-11-11T09:15:00Z. Empty if NTP not synced yet
// (the backend then uses its own clock).
String isoTimestamp() {
  struct tm t;
  if (!getLocalTime(&t, 200)) return "";
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &t);
  return String(buf);
}

String uidToString(MFRC522::Uid &uid) {
  String s = "";
  for (byte i = 0; i < uid.size; i++) {
    if (uid.uidByte[i] < 0x10) s += "0";
    s += String(uid.uidByte[i], HEX);
  }
  s.toUpperCase();
  return s;
}

// Sends the scan and updates LCD/LEDs/buzzer from the answer.
void sendScan(const String &cardUid) {
  if (WiFi.status() != WL_CONNECTED) {
    connectWifi();
    if (WiFi.status() != WL_CONNECTED) {
      showLcd("No network", "Try again");
      signalFailure();
      return;
    }
  }

  showLcd("Checking...", cardUid);

  StaticJsonDocument<256> req;
  req["device_id"] = DEVICE_ID;
  req["card_uid"] = cardUid;
  String ts = isoTimestamp();
  if (ts.length()) req["timestamp"] = ts;
  String body;
  serializeJson(req, body);

  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_API_KEY);
  int code = http.POST(body);

  if (code <= 0) {
    showLcd("Server error", "No response");
    signalFailure();
    http.end();
    return;
  }

  String payload = http.getString();
  http.end();

  StaticJsonDocument<768> res;
  DeserializationError err = deserializeJson(res, payload);
  if (err) {
    showLcd("Bad response", String("HTTP ") + code);
    signalFailure();
    return;
  }

  bool success = res["success"] | false;
  const char *status = res["status"] | "ERROR";

  if (code == 200 && success) {
    const char *student = res["student"] | "";
    const char *course = res["course"] | "";
    showLcd(String(student), String(status) + " " + String(course));
    signalSuccess();
  } else {
    const char *msg = res["message"] | "";
    showLcd(String(status), String(msg));
    signalFailure();
  }
}

// ---------------- Arduino entry points ----------------
void setup() {
  Serial.begin(115200);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  Wire.begin(LCD_SDA, LCD_SCL);
  lcd.init();
  lcd.backlight();
  showLcd("Starting...");

  SPI.begin(RC522_SCK, RC522_MISO, RC522_MOSI, RC522_SDA);
  rfid.PCD_Init();

  // Self-test of all indicators
  digitalWrite(LED_GREEN, HIGH); digitalWrite(LED_RED, HIGH); beep(80);
  delay(300);
  digitalWrite(LED_GREEN, LOW); digitalWrite(LED_RED, LOW);

  connectWifi();
  syncTime();
  showReady();
  Serial.println("Ready");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED && millis() % 10000 < 50) {
    WiFi.reconnect();
  }

  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    delay(30);
    return;
  }

  String uid = uidToString(rfid.uid);
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();

  // Local debounce: ignore the same card tapped again within the cooldown.
  if (uid == lastUid && millis() - lastScanAt < CARD_COOLDOWN_MS) {
    return;
  }
  lastUid = uid;
  lastScanAt = millis();

  Serial.println("Card: " + uid);
  sendScan(uid);

  delay(1500);
  showReady();
}
