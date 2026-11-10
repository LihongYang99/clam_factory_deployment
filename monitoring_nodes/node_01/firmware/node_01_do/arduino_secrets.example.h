#pragma once
#include <stdint.h>
// Copy to arduino_secrets.h (Git-ignored); never commit real credentials.
constexpr char WIFI_SSID[] = "YOUR_2_4_GHZ_SSID";
constexpr char WIFI_PASSWORD[] = "YOUR_WIFI_PASSWORD";

// Empty host disables MQTT for the initial USB + Wi-Fi commissioning step.
constexpr char MQTT_HOST[] = "";
constexpr uint16_t MQTT_PORT = 1883;
constexpr char MQTT_USER[] = "";
constexpr char MQTT_PASSWORD[] = "";
constexpr char NTP_SERVER[] = "192.168.88.250";
