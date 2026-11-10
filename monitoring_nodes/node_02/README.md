# Node 02 — ORP and temperature

DFRobot SEN0709, ESP32-S3 with 16 MB flash and 8 MB OPI PSRAM.
Board MAC: `30:30:F9:3B:81:B4`. Reserve `192.168.88.102` in the router;
firmware uses DHCP. Native USB CDC carries diagnostics (unlike Node 01 UART0).

## Wiring

Disconnect power before wiring. GPIO17 TX → converter RXD; GPIO18 RX ←
converter TXD. Connect sensor A/B to converter A/B. Use the verified converter
power and grounding arrangement. Never connect 12 V to an ESP32 5 V pin.

## Firmware

`firmware/node_02_orp` polls address 1 at 4800 baud, 8N1 every five seconds.
Only Modbus function 03 is sent: signed ORP mV and signed temperature / 10.
CRC or frame errors produce null readings, not zero. Calibration is UNVERIFIED.
Protocol reference: https://wiki.dfrobot.com/sen0709/docs/23382

Copy `arduino_secrets.example.h` to `arduino_secrets.h` and fill Wi-Fi settings.
The local file is Git-ignored. NTP uses Jetson `192.168.88.250`.
MQTT remains disabled until a separate Node 02 account and broker ACL are ready.
Do not reuse Node 01 credentials. Prepared topics are `clam/node_02/telemetry`
and `clam/node_02/status`; gateway/dashboard integration is still pending.

## Compile and upload on Mac

```bash
cd /Users/lihongyang/Documents/clam_factory_deployment
ARDUINO_CLI="/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli"
CLAM_SKETCH="monitoring_nodes/node_02/firmware/node_02_orp"
CLAM_FQBN="esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc,UploadSpeed=115200"
"$ARDUINO_CLI" compile --fqbn "$CLAM_FQBN" --build-path build/node_02/arduino "$CLAM_SKETCH"
ls /dev/cu.*
# Set this to the current Node 02 USB port; it can change after reset.
CLAM_PORT=/dev/cu.usbmodem11301
"$ARDUINO_CLI" upload --port "$CLAM_PORT" --fqbn "$CLAM_FQBN" --input-dir build/node_02/arduino "$CLAM_SKETCH"
"$ARDUINO_CLI" monitor --port "$CLAM_PORT" --config baudrate=115200 --config dtr=on --config rts=off
```

If connection fails, hold BOOT, press/release RESET, release BOOT, then list ports
again. Close the serial monitor before uploading. Check `sensor_status: OK`,
actual `orp_mv` / `temperature_c`, and `clock_status: SYNCED` after NTP succeeds.

## Protocol check

```bash
c++ -std=c++11 monitoring_nodes/node_02/tests/protocol_test.cpp -o /tmp/clam-node02-protocol-test
/tmp/clam-node02-protocol-test
```

Checks manufacturer example, negative readings, CRC rejection and timeout.
No calibration registers are written by this firmware.

## Bench verification — November 10, 2026

Uploaded firmware 0.1.0 and verified flash hashes. After manual RESET, USB
telemetry reported SEN0709 response OK, ORP 254 mV and temperature 22.5 °C.
Wi-Fi connected with DHCP address `192.168.88.98`; the `.102` reservation still
needs to be applied. NTP reached SYNCED with a UTC sample timestamp. MQTT is
intentionally disabled. These checks confirm communication, not calibration
or measurement accuracy; no calibration commands were sent.

## Enable MQTT and deploy the dashboard

Local firmware now supports MQTT as `clam_node_02`; enter that account's password
in the ignored secrets file and rebuild/upload. The gateway accepts Node 02 and
serves `/api/node_02`. ORP and its temperature have separate detail views and
remain distinct from Node 01 readings. Local tests do not prove deployment.

On the Mac:

```bash
rsync -av --exclude='.env' --exclude='__pycache__/' gateway web lihong@192.168.88.250:~/clam_factory_deployment/
```

On the Jetson, from `~/clam_factory_deployment`:

```bash
sudo install -o root -g mosquitto -m 640 gateway/mosquitto/clam.acl /etc/mosquitto/clam.acl
sudo systemctl restart mosquitto
sudo systemctl restart clam-gateway
systemctl is-active mosquitto clam-gateway
```

The existing broker password file and gateway `.env` must be preserved.
