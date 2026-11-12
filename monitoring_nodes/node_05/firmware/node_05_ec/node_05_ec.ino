#include <Arduino.h>
#include <WiFi.h>
#include <MQTT.h>
#include <esp_sntp.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <time.h>
#include "Protocol.h"
#include "Calibration.h"
#include "arduino_secrets.h"

constexpr char NODE_ID[] = "node_05";
constexpr char VERSION[] = "0.1.4";
constexpr char TELEMETRY_TOPIC[] = "clam/node_05/telemetry";
constexpr char STATUS_TOPIC[] = "clam/node_05/status";
constexpr int EC_TX = 17;
constexpr int EC_RX = 18;
constexpr double PROBE_K = 10.0;  // Physical probe confirmed by the operator.
constexpr uint32_t POLL_MS = 5000;
constexpr uint32_t RESPONSE_MS = 1800;
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
bool probeReady = false;
bool kWriteAttempted = false;
double configuredK = NAN;
double compensationTemperature = NAN;
ezoec::Calibration calibration;

void onTimeSync(struct timeval*) { clockSynced = true; }

void printLine(const char* line) {
  if (Serial) Serial.println(line); else ++serialSkipped;
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
  if (mqtt.connected()) mqtt.loop();
  else if (now - lastMqttAttempt >= 5000) {
    lastMqttAttempt = now;
    if (mqtt.connect(clientId, MQTT_USER, MQTT_PASSWORD))
      mqtt.publish(STATUS_TOPIC, "{\"node_id\":\"node_05\",\"online\":true}", true, 1);
    else printLine("event=MQTT_CONNECT_FAILED check_broker_address_credentials_and_LAN");
  }
}

const char* transact(const char* command, bool needsData, ezoec::Reply& reply) {
  delay(200);
  while (probe.available()) probe.read();
  reply = ezoec::Reply{};
  probe.print(command);
  probe.write('\r');
  probe.flush();
  const uint32_t start = millis();
  while (!reply.done && millis() - start < RESPONSE_MS) {
    while (probe.available() && !reply.done) reply.push(uint8_t(probe.read()));
    delay(1);
  }
  return reply.result(needsData);
}

const char* initializeProbe(ezoec::Reply& reply) {
  configuredK = NAN;
  compensationTemperature = NAN;
  // Stop inherited continuous output before requesting acknowledged transactions.
  probe.print("C,0\r");
  probe.flush();
  delay(1200);
  const char* error = transact("*OK,1", false, reply);
  if (error) return error;
  if ((error = transact("i", true, reply))) return error;
  if (!ezoec::startsWith(reply.data, "?I,EC,")) return "WRONG_SENSOR";
  if ((error = transact("Status", true, reply))) return error;
  if (!ezoec::startsWith(reply.data, "?Status,")) return "UNEXPECTED_FRAME";
  char power[96];
  snprintf(power, sizeof(power), "event=EC_POWER response=%s", reply.data);
  printLine(power);
  if ((error = transact("K,?", true, reply))) return error;
  if (!ezoec::setting(reply.data, "?K,", configuredK) || configuredK <= 0)
    return "INVALID_CONFIG";
  if ((error = transact("T,?", true, reply))) return error;
  if (!ezoec::setting(reply.data, "?T,", compensationTemperature)) return "INVALID_CONFIG";
  if ((error = transact("Cal,?", true, reply))) return error;
  double calibration = 0;
  if (!ezoec::setting(reply.data, "?Cal,", calibration) ||
      calibration < 0 || calibration > 2 || calibration != floor(calibration))
    return "INVALID_CONFIG";
  char settings[180];
  snprintf(settings, sizeof(settings),
           "event=EC_CONFIG probe_k=%.2f expected_k=%.2f compensation_temperature_c=%.2f cal_mode=%d",
           configuredK, PROBE_K, compensationTemperature, int(calibration));
  printLine(settings);
  if (fabs(configuredK - PROBE_K) > 0.001) {
    // Set the confirmed K10 probe type only on an uncalibrated circuit.
    if (calibration != 0 || kWriteAttempted) return "CONFIG_MISMATCH";
    kWriteAttempted = true;
    printLine("event=EC_K_CONFIGURING target=10 cal_mode=0");
    if ((error = transact("K,10", false, reply))) return error;
    if ((error = transact("K,?", true, reply))) return error;
    if (!ezoec::setting(reply.data, "?K,", configuredK) ||
        fabs(configuredK - PROBE_K) > 0.001) return "CONFIG_MISMATCH";
    printLine("event=EC_K_CONFIRMED probe_k=10 calibration=UNVERIFIED");
  }
  for (const char* command : {"O,EC,1", "O,TDS,0", "O,S,1", "O,SG,0"}) {
    if ((error = transact(command, false, reply))) return error;
  }
  printLine("event=EC_READY output=EC,S units=uS_cm,PSU calibration=UNVERIFIED compensation=UNVERIFIED");
  return nullptr;
}

void sample() {
  ++sequence;
  ezoec::Reply reply;
  const char* error = nullptr;
  // Continue reading after transient errors in CAL mode without changing settings.
  if (!probeReady && !calibration.active) {
    error = initializeProbe(reply);
    probeReady = !error;
  }
  const uint64_t sampleUptimeMs = esp_timer_get_time() / 1000;
  char timestamp[32] = "null";
  const bool syncedAtSample = clockSynced;
  if (syncedAtSample) {
    time_t now = time(nullptr);
    struct tm utc;
    gmtime_r(&now, &utc);
    strftime(timestamp, sizeof(timestamp), "\"%Y-%m-%dT%H:%M:%SZ\"", &utc);
  }
  double conductivity = 0, salinity = NAN;
  if (!error) error = transact("R", true, reply);
  if (!error) error = ezoec::measurements(reply.data, conductivity, salinity);
  if (error) probeReady = false;

  char raw[257] = "";
  for (size_t i = 0; i < reply.count; ++i) snprintf(raw + i * 2, 3, "%02X", reply.raw[i]);
  char salt[32] = "null";
  if (!error && std::isfinite(salinity)) snprintf(salt, sizeof(salt), "%.8g", salinity);
  char ec[32] = "null", k[24] = "null", temp[24] = "null";
  if (!error) snprintf(ec, sizeof(ec), "%.8g", conductivity);
  if (std::isfinite(configuredK)) snprintf(k, sizeof(k), "%.6g", configuredK);
  if (std::isfinite(compensationTemperature)) snprintf(temp, sizeof(temp), "%.6g", compensationTemperature);
  char payload[1280];
  const int length = snprintf(payload, sizeof(payload),
      "{\"schema_version\":1,\"node_id\":\"%s\",\"sensor_model\":\"EZO-EC\","
      "\"firmware_version\":\"%s\",\"boot_id\":\"%s\",\"sequence\":%lu,"
      "\"sample_time_utc\":%s,\"uptime_ms\":%llu,\"clock_status\":\"%s\","
      "\"conductivity_us_cm\":%s,\"salinity_psu\":%s,\"probe_k\":%s,\"compensation_temperature_c\":%s,"
      "\"sensor_status\":\"%s\",\"calibration_status\":\"UNVERIFIED\","
      "\"compensation_status\":\"UNVERIFIED\",\"raw_hex\":\"%s\","
      "\"raw_truncated\":%s,\"not_forwarded_before_sample\":%lu}",
      NODE_ID, VERSION, bootId, (unsigned long)sequence, timestamp,
      (unsigned long long)sampleUptimeMs, syncedAtSample ? "SYNCED" : "UNSYNCED",
      ec, salt, k, temp, error ? error : "OK", raw, reply.truncated ? "true" : "false",
      (unsigned long)notForwarded);
  if (length < 0 || size_t(length) >= sizeof(payload)) {
    ++notForwarded;
    printLine("event=PAYLOAD_OVERFLOW");
    return;
  }
  printLine(payload);
  if (calibration.active) return;  // Standards must not enter the process history.
  // shortcut: no offline queue; add durable buffering before unattended research logging.
  if (!mqtt.connected() || !mqtt.publish(TELEMETRY_TOPIC, payload, false, 1)) ++notForwarded;
}

const char* calibrationSettings(ezoec::Reply& reply, double& mode) {
  const char* error = transact("K,?", true, reply);
  if (error) return error;
  if (!ezoec::setting(reply.data, "?K,", configuredK)) return "INVALID_CONFIG";
  if ((error = transact("T,?", true, reply))) return error;
  if (!ezoec::setting(reply.data, "?T,", compensationTemperature)) return "INVALID_CONFIG";
  if ((error = transact("Cal,?", true, reply))) return error;
  if (!ezoec::setting(reply.data, "?Cal,", mode) || mode < 0 || mode > 2 || mode != floor(mode))
    return "INVALID_CONFIG";
  return nullptr;
}

void calibrationStatus() {
  ezoec::Reply reply;
  double mode = NAN;
  const char* error = calibrationSettings(reply, mode);
  char line[240];
  snprintf(line, sizeof(line),
           "event=CAL_STATUS mode=%s next=%s result=%s probe_k=%.2f compensation_temperature_c=%.2f cal_mode=%.0f calibration_status=UNVERIFIED",
           calibration.active ? "ON" : "OFF", calibration.stage(), error ? error : "OK",
           configuredK, compensationTemperature, mode);
  printLine(line);
  if (calibration.active && calibration.next == ezoec::Calibration::VERIFY)
    printLine(!error && calibration.sequenceConfirmed(mode)
        ? "event=CAL_SEQUENCE_CONFIRMED standard_rechecks_required=true calibration_status=UNVERIFIED"
        : "event=CAL_SEQUENCE_NOT_CONFIRMED check_CAL_STATUS do_not_repeat_writes=true");
}

void calibrate(ezoec::Calibration::Step step, const char* command, double target) {
  const char* error = calibration.check(step);
  ezoec::Reply reply;
  double mode = NAN, reading = NAN, salinity = NAN;
  if (!error) error = transact("i", true, reply);
  if (!error && !ezoec::startsWith(reply.data, "?I,EC,")) error = "WRONG_SENSOR";
  if (!error) error = calibrationSettings(reply, mode);
  if (!error && fabs(configuredK - PROBE_K) > 0.001) error = "K10_REQUIRED";
  if (!error && fabs(compensationTemperature - 25.0) > 0.001) error = "T25_REQUIRED";
  // Dry calibration can correct a nonzero air reading; dryness is operator-confirmed.
  if (!error && step != ezoec::Calibration::DRY) {
    error = transact("R", true, reply);
    if (!error) error = ezoec::measurements(reply.data, reading, salinity);
    if (!error && reading == 0) error = "ZERO_READING_IN_STANDARD";
    if (!error && fabs(reading - target) > target * 0.4)
      printLine("event=CAL_READING_WARNING outside_approximate_40_percent=true");
  }
  if (error) {
    char line[160];
    snprintf(line, sizeof(line), "event=CAL_COMMAND_REJECTED reason=%s next=%s", error, calibration.stage());
    printLine(line);
    return;
  }
  // Only this explicit USB command writes calibration; never retry uncertain writes.
  error = transact(command, false, reply);
  char raw[257] = "";
  for (size_t i = 0; i < reply.count; ++i) snprintf(raw + i * 2, 3, "%02X", reply.raw[i]);
  char line[400];
  snprintf(line, sizeof(line), "event=CAL_REPLY command=%s result=%s raw_hex=%s", command, error ? error : "ACK", raw);
  printLine(line);
  calibration.written(!error);
  if (error) {
    printLine("event=CAL_WRITE_UNCONFIRMED no_auto_retry=true restart_full_procedure_if_needed=true");
    return;
  }
  snprintf(line, sizeof(line), "event=CAL_STEP_ACK next=%s calibration_status=UNVERIFIED", calibration.stage());
  printLine(line);
  calibrationStatus();  // Intermediate Cal,? modes are not interpreted as step ACKs.
}

void serviceCalibration() {
  static ezoec::CalibrationInput input;
  while (Serial.available()) {
    if (!input.push(char(Serial.read()))) continue;
    if (input.invalid) printLine("event=CAL_COMMAND_REJECTED reason=INVALID_LINE");
    else if (!input.text[0]) { /* Ignore blank lines. */ }
    else if (!strcmp(input.text, "CAL STATUS")) calibrationStatus();
    else if (!strcmp(input.text, "CAL BEGIN")) {
      calibration.begin();
      printLine("event=CAL_MODE telemetry_paused=true serial_readings_continue=true");
      calibrationStatus();
    } else if (!strcmp(input.text, "CAL DRY CONFIRM"))
      calibrate(ezoec::Calibration::DRY, "Cal,dry", 0);
    else if (!strcmp(input.text, "CAL LOW 12880 CONFIRM"))
      calibrate(ezoec::Calibration::LOW_POINT, "Cal,low,12880", 12880);
    else if (!strcmp(input.text, "CAL HIGH 150000 CONFIRM"))
      calibrate(ezoec::Calibration::HIGH_POINT, "Cal,high,150000", 150000);
    else if (!strcmp(input.text, "CAL END")) {
      calibration.end();
      printLine("event=CAL_MODE telemetry_paused=false calibration_status=UNVERIFIED");
    } else printLine("event=CAL_COMMAND_REJECTED reason=UNKNOWN_COMMAND");
    input = {};
  }
}

void setup() {
  Serial.begin(115200);
  printLine("event=BOOT node=node_05 firmware=0.1.4");
  probe.begin(9600, SERIAL_8N1, EC_RX, EC_TX);
  snprintf(bootId, sizeof(bootId), "%08lx%08lx", (unsigned long)esp_random(), (unsigned long)esp_random());
  snprintf(clientId, sizeof(clientId), "clam-node05-%012llx", (unsigned long long)ESP.getEfuseMac());
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  sntp_set_time_sync_notification_cb(onTimeSync);
  configTime(0, 0, NTP_SERVER);
  if (MQTT_ENABLED) {
    mqtt.begin(MQTT_HOST, MQTT_PORT, network);
    mqtt.setOptions(15, true, 1000);
    network.setConnectionTimeout(1000);
    mqtt.setWill(STATUS_TOPIC, "{\"node_id\":\"node_05\",\"online\":false}", true, 1);
  }
  delay(2000);  // EZO circuit boot grace period.
  lastPoll = millis() - POLL_MS;
  lastStatus = millis() - 10000;
}

void loop() {
  serviceNetwork();
  serviceCalibration();
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
