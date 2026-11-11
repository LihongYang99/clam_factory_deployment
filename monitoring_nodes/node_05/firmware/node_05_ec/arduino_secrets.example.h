#pragma once
#include <stdint.h>
// Copy to arduino_secrets.h (Git-ignored); never commit real credentials.
constexpr char WIFI_SSID[] = "YOUR_2_4_GHZ_SSID";
constexpr char WIFI_PASSWORD[] = "YOUR_WIFI_PASSWORD";

// MQTT stays disabled until the separate clam_node_05 account is ready.
constexpr char MQTT_HOST[] = "192.168.88.250";
constexpr uint16_t MQTT_PORT = 1883;
constexpr char MQTT_USER[] = "clam_node_05";
constexpr char MQTT_PASSWORD[] = "";
constexpr char NTP_SERVER[] = "192.168.88.250";
