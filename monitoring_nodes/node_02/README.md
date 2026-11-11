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
Normal acquisition uses Modbus function 03: signed ORP mV and signed temperature / 10.
Firmware 0.1.2 additionally supports explicit USB-only function 16 calibration writes.
CRC or frame errors produce null readings, not zero. Calibration is UNVERIFIED.
Protocol reference: https://wiki.dfrobot.com/sen0709/docs/23382

Copy `arduino_secrets.example.h` to `arduino_secrets.h` and fill Wi-Fi settings.
The local file is Git-ignored. NTP uses Jetson `192.168.88.250`.
MQTT remains disabled until a separate Node 02 account and broker ACL are ready.
Do not reuse Node 01 credentials. Prepared topics are `clam/node_02/telemetry`
and `clam/node_02/status`; gateway/dashboard integration is available below.

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
Normal acquisition never writes calibration registers; only the manual commands below do.

## Initial bench verification — November 10, 2026 (historical)

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

## Manual ORP calibration (USB, firmware 0.1.2)

**Calibration writes are on hold after an undocumented reply in firmware 0.1.3.**
See the [calibration review](calibration_review.md) before following the steps below.
The steps describe the implemented low-to-high sequence, whose compatibility with
this probe is not yet established. Do not retry or reverse the points based on
another model's manual. No additional upload is needed for this review.

Use the SEN0709 two-point procedure. These commands use the Hach bottle nominal
values (200 and 600 mV); temperature correction and batch-certified values have
not been verified. Do not describe this as certified accuracy verification.

1. Upload firmware 0.1.2. Open a bidirectional serial terminal at 115200 baud,
   with newline enabled. Send `CAL BEGIN` before immersing in standards.
   MQTT telemetry pauses; USB readings continue. A reboot leaves calibration mode.
2. Rinse the probe and immerse it in the 200 mV standard. After stabilization,
   send `CAL POINT1 200 CONFIRM`. Expect `CAL_POINT_1_ACK`.
3. Rinse, immerse in the 600 mV standard, and wait for stabilization.
   Send `CAL POINT2 600 CONFIRM`. Expect `CAL_POINT_2_ACK`.
4. While still in calibration mode, remeasure fresh portions of both standards.
   Record before/after readings, temperatures, solution lots, expiry and date.
   An acknowledgement alone does not establish calibration accuracy.
5. Rinse and return the probe to the monitored water, then send `CAL END`.
   This resumes telemetry; it does not undo sensor calibration writes.

Commands are case-sensitive. Point 2 requires an acknowledged point 1 in the
same session. If a write is unconfirmed, its outcome is unknown; do not assume
nothing changed. Resolve the unconfirmed reply before attempting another write.
Calibration status remains UNVERIFIED pending review of post-calibration readings.
No automatic calibration date or verified status is published by this version.

Protocol reference: https://wiki.dfrobot.com/sen0709/docs/23382

### Guided session: upload, open the terminal, calibrate

Run upload commands on the **Mac**, not inside the Jetson SSH session.
Keep Node 02 connected to USB and the probe powered. Close any serial monitor
before uploading. Do not overwrite the existing `arduino_secrets.h`.

1. Run the compile/upload block above, stopping before its `monitor` command.
   The observed Node 02 port was `/dev/cu.usbmodem11301`; recheck with
   `ls /dev/cu.*` if it disappears. Stop if compilation or upload reports an error.
2. Open `firmware/node_02_orp/node_02_orp.ino` in Arduino IDE. Select the Node 02
   port, open Serial Monitor, set **115200 baud** and **Newline**. Do not open a
   second terminal on the same port. If necessary press RESET once, without BOOT.
   Confirm firmware `0.1.2` and valid ORP/temperature readings.
3. In the Serial Monitor input, send `CAL BEGIN`. Expect:
   `event=CAL_MODE telemetry_paused=true serial_readings_continue=true`.
   The dashboard may become stale during calibration; use USB readings.
4. Rinse and immerse in 200 mV solution; wait for stable ORP and temperature.
   Send exactly `CAL POINT1 200 CONFIRM`. Continue only after `CAL_POINT_1_ACK`.
5. Rinse and immerse in 600 mV solution; wait again.
   Send exactly `CAL POINT2 600 CONFIRM`. Expect `CAL_POINT_2_ACK`.
   Each command writes to the probe immediately; past recorded readings alone
   cannot substitute for having the probe in the corresponding solution.
6. Still in calibration mode, rinse between fresh portions of both standards
   and record post-calibration values and temperatures. Report both readings
   before claiming success. The original readings were 195 mV at 21.8 C and
   587 mV at 21.7 C. The 600 mV bottle is Hach 25M2A1002-115, lot 6224,
   manufactured Aug 2026, expiry Aug 2027. The 200 mV bottle is 25M2A1001-115;
   its batch is not recorded. Both were reported unexpired by the operator.
7. Return the rinsed probe to monitored water and send `CAL END`.
   Confirm telemetry resumes. This command does not roll back calibration.

Keep the same power/session between the two calibration points. If the board
reboots, send `CAL BEGIN` again and repeat both points. Calibration mode is not
persistent and telemetry resumes after reboot; keep standard-solution samples
out of research data if a reboot occurs.

Frame generation check (compares against the manufacturer's two examples):

```bash
c++ -std=c++11 monitoring_nodes/node_02/tests/calibration_test.cpp -o /tmp/clam-node02-calibration-test
/tmp/clam-node02-calibration-test
```

### Firmware 0.1.2: serial command troubleshooting

Leading/trailing spaces and tabs are accepted; backspace and Delete edit the
input line. Empty lines are ignored. Overlong lines remain rejected.
`CAL STATUS` reports mode and whether point 1 was acknowledged. Repeating
`CAL BEGIN` while already in calibration mode preserves point 1.
Rejections now distinguish `MODE_OFF`, `POINT1_REQUIRED`, `UNKNOWN_COMMAND`,
and `LINE_TOO_LONG`. Hidden terminal escape sequences are not accepted.

Uploading resets the
in-memory calibration session: after an upgrade, repeat both points in their
respective solutions. It does not restore the probe's previous coefficients.
Do not bypass the first-point requirement to resume an interrupted session.

### Mac terminal alternative (no Arduino IDE required)

After uploading, open the serial monitor:

```bash
"/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli" monitor \
  --port /dev/cu.usbmodem11301 \
  --config baudrate=115200 --config dtr=on --config rts=off
```

Type commands into that running monitor and press Enter (not at a shell prompt).
Send `CAL BEGIN`, then `CAL STATUS`. Expect `mode=ON point1_ack=false`.
With the probe stable in 200 mV solution, send `CAL POINT1 200 CONFIRM`.
After `CAL_POINT_1_ACK`, `CAL STATUS` must report `point1_ack=true`.
Only then rinse, move to 600 mV, stabilize and send `CAL POINT2 600 CONFIRM`.
Do not paste the entire sequence at once. Complete post-calibration checks
before returning to monitored water and sending `CAL END`.

If rejected, read the `reason` field and send `CAL STATUS`; do not repeatedly
write calibration points without diagnosing the cause. Ctrl+C closes the monitor.

### Firmware 0.1.3: inspect calibration responses

Each explicit calibration write now prints `event=CAL_REPLY` with point number,
received byte count, elapsed milliseconds, result and raw hexadecimal response.
The response must pass CRC, address, function, register and quantity checks.
`TIMEOUT`, `SHORT_FRAME`, `CRC_ERROR`, `WRONG_ADDRESS`, `MODBUS_EXCEPTION`,
`UNEXPECTED_FRAME` and `FRAME_OVERFLOW` remain unconfirmed outcomes; there is
no automatic retry. Normal function-03 reading success does not confirm a
function-16 calibration write. Capture the diagnostic before retrying.
This version does not change the calibration targets or automatically calibrate.
