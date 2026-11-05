#include <Arduino.h>
#include <WiFi.h>
#include <MQTT.h>
#include <esp_sntp.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <time.h>
#include "Protocol.h"
#include "SerialLog.h"
#include "arduino_secrets.h"

constexpr char NODE_ID[] = "node_01";
constexpr char VERSION[] = "0.1.3";
constexpr char TELEMETRY_TOPIC[] = "clam/node_01/telemetry";
constexpr char STATUS_TOPIC[] = "clam/node_01/status";
constexpr int DO_TX = 17;
constexpr int DO_RX = 18;
constexpr uint32_t POLL_MS = 5000;
constexpr uint32_t RESPONSE_MS = 1000;
constexpr bool MQTT_ENABLED = MQTT_HOST[0] && MQTT_USER[0] && MQTT_PASSWORD[0];

HardwareSerial probe(1);
WiFiClient network;
MQTTClient mqtt(256, 1536);
char bootId[17];
char clientId[40];
uint32_t sequence = 0;
uint32_t notForwarded = 0;
uint32_t serialSkipped = 0;
volatile bool clockSynced = false;
uint32_t lastWifiAttempt = 0;
uint32_t lastMqttAttempt = 0;
uint32_t lastStatus = 0;
uint32_t lastPoll = 0;

void onTimeSync(struct timeval*) { clockSynced = true; }

void printLine(const char* line) {
  if (!writeLogLine(Serial0, line)) ++serialSkipped;
}

void serviceNetwork() {
  const uint32_t now = millis();
  if (WiFi.status() != WL_CONNECTED) {
    if (now - lastWifiAttempt >= 15000) {
      lastWifiAttempt = now;
      WiFi.reconnect();
    }
    return;
  }
  if (!MQTT_ENABLED) return;
  if (mqtt.connected()) {
    mqtt.loop();
  } else if (now - lastMqttAttempt >= 5000) {
    lastMqttAttempt = now;
    if (mqtt.connect(clientId, MQTT_USER, MQTT_PASSWORD)) {
      mqtt.publish(STATUS_TOPIC, "{\"node_id\":\"node_01\",\"online\":true}", true, 1);
    } else {
      printLine("event=MQTT_CONNECT_FAILED check_broker_address_credentials_and_LAN");
    }
  }
}

void sample() {
  ++sequence;
  const uint64_t sampleUptimeMs = esp_timer_get_time() / 1000;
  char timestamp[32] = "null";
  const bool syncedAtSample = clockSynced;
  if (syncedAtSample) {
    time_t now = time(nullptr);
    struct tm utc;
    gmtime_r(&now, &utc);
    strftime(timestamp, sizeof(timestamp), "\"%Y-%m-%dT%H:%M:%SZ\"", &utc);
  }

  while (probe.available()) probe.read();
  probe.write(sen0681::request, sizeof(sen0681::request));
  probe.flush();
  uint8_t bytes[64];
  size_t count = 0;
  bool overflow = false;
  const uint32_t started = millis();
  uint32_t lastByte = started;
  while (millis() - started < RESPONSE_MS) {
    while (probe.available()) {
      const int byte = probe.read();
      if (count < sizeof(bytes)) bytes[count++] = uint8_t(byte);
      else overflow = true;
      lastByte = millis();
    }
    // At 4800 baud a 20 ms quiet gap exceeds Modbus frame separation.
    if (count && millis() - lastByte >= 20) break;
    delay(1);
  }

  sen0681::Reading reading{};
  const char* error = overflow ? "FRAME_OVERFLOW" : sen0681::decode(bytes, count, reading);
  char raw[129] = "";
  for (size_t i = 0; i < count; ++i) snprintf(raw + i * 2, 3, "%02X", bytes[i]);
  char values[160] = "\"do_mg_l\":null,\"saturation_pct\":null,\"temperature_c\":null";
  if (!error) {
    snprintf(values, sizeof(values), "\"do_mg_l\":%.4f,\"saturation_pct\":%.4f,\"temperature_c\":%.4f",
             reading.do_mg_l, reading.saturation_pct, reading.temperature_c);
  }
  char payload[1024];
  const int length = snprintf(payload, sizeof(payload),
      "{\"schema_version\":1,\"node_id\":\"%s\",\"sensor_model\":\"SEN0681\","
      "\"firmware_version\":\"%s\",\"boot_id\":\"%s\",\"sequence\":%lu,"
      "\"sample_time_utc\":%s,\"uptime_ms\":%llu,\"clock_status\":\"%s\","
      "%s,\"sensor_status\":\"%s\",\"calibration_status\":\"UNVERIFIED\","
      "\"compensation_status\":\"UNVERIFIED\",\"raw_hex\":\"%s\","
      "\"raw_truncated\":%s,\"not_forwarded_before_sample\":%lu}",
      NODE_ID, VERSION, bootId, (unsigned long)sequence, timestamp,
      (unsigned long long)sampleUptimeMs, syncedAtSample ? "SYNCED" : "UNSYNCED",
      values, error ? error : "OK", raw, overflow ? "true" : "false",
      (unsigned long)notForwarded);
  if (length < 0 || size_t(length) >= sizeof(payload)) {
    ++notForwarded;
    printLine("event=PAYLOAD_OVERFLOW");
    return;
  }
  printLine(payload);
  // shortcut: no offline queue; add durable buffering before unattended research logging.
  if (!mqtt.connected() || !mqtt.publish(TELEMETRY_TOPIC, payload, false, 1))
    ++notForwarded;
}

void setup() {
  // The connected WCH USB bridge carries UART0, not native USB CDC.
  Serial0.setTxBufferSize(2048);
  Serial0.begin(115200);
  printLine("event=BOOT node=node_01 firmware=0.1.3");
  probe.begin(4800, SERIAL_8N1, DO_RX, DO_TX);
  printLine("event=UART_READY");
  snprintf(bootId, sizeof(bootId), "%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random());
  snprintf(clientId, sizeof(clientId), "clam-node01-%012llx", (unsigned long long)ESP.getEfuseMac());
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  printLine("event=WIFI_STARTED");
  sntp_set_time_sync_notification_cb(onTimeSync);
  configTime(0, 0, NTP_SERVER);
  if (MQTT_ENABLED) {
    mqtt.begin(MQTT_HOST, MQTT_PORT, network);
    mqtt.setOptions(15, true, 1000);
    network.setConnectionTimeout(1000);
    mqtt.setWill(STATUS_TOPIC, "{\"node_id\":\"node_01\",\"online\":false}", true, 1);
  }
  lastPoll = millis() - POLL_MS;
  lastStatus = millis() - 10000;
  printLine("event=SETUP_DONE");
}

void loop() {
  serviceNetwork();
  const uint32_t now = millis();
  if (now - lastPoll >= POLL_MS) {
    lastPoll = now;
    sample();
  }
  if (now - lastStatus >= 10000) {
    lastStatus = now;
    char status[320];
    snprintf(status, sizeof(status),
        "event=STATUS node=%s mac=%s ip=%s wifi=%s mqtt=%s rssi=%d not_forwarded=%lu serial_skipped=%lu",
        NODE_ID, WiFi.macAddress().c_str(), WiFi.localIP().toString().c_str(),
        WiFi.status() == WL_CONNECTED ? "CONNECTED" : "DISCONNECTED",
        !MQTT_ENABLED ? "DISABLED" : mqtt.connected() ? "CONNECTED" : "DISCONNECTED",
        WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0,
        (unsigned long)notForwarded, (unsigned long)serialSkipped);
    printLine(status);
  }
  delay(1);
}
