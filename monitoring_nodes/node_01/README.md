# Node 01 — Dissolved Oxygen

**Device ID:** `node_01`  
**Scope:** read DO and temperature, then publish measurements over Wi-Fi to the
Jetson gateway. No ORP channel or actuator control on this board.

**Status:** v0.1.3 runtime confirmed by user-provided serial logs: UART0 console,
Wi-Fi connection, DHCP address, and 5-second polling are working. Sensor reads
now report OK with DO, saturation, and temperature; sample UTC is UNSYNCED;
MQTT delivery to Jetson was verified by two subscriber messages on 2026-11-06
(see [gateway verification](../../gateway/README.md#verified-node-01-reception--2026-11-06)).
WebFig confirms the active lease is `192.168.88.101` after board reset
(2026-11-04). Sensor values reach the Jetson broker; calibration and compensation remain
unverified. Database recording and the dashboard are pending.
See [LAN address reservations](../../docs/network_setup.md) for setup and verification.
The instructions below target ESP32-S3 N16R8 + SEN0681; stop if your labels differ.

## Hardware to identify

Board, probe, and converter models below come from the earlier shrimp project
and still require label verification. Power details were reported by the owner.

| Part | Reference model | New-project verification |
| --- | --- | --- |
| Board | ESP32-S3 N16R8 | Confirm board label and USB port |
| DO probe | DFRobot SEN0681 | Confirm exact model |
| Serial converter | Waveshare TTL TO RS485 (B), 23778 | Confirm variant and terminal labels |
| External power supply | 12 V DC, 5 A rated output | Owner-reported; exact model and distribution wiring pending |
| Board supply | Regulated 5 V through the board 5V and GND pins | Owner-reported; source of the 5 V rail pending |

Do not connect sensor supply voltage or RS485 A/B directly to ESP32 GPIO.
The previous installation used GPIO17 TX and GPIO18 RX for DO; these are
reference assignments only, not a verified wiring instruction for this board.
Final wiring must describe converter direction, power domains, and grounding
against the actual parts. The Waveshare documentation could not be fetched
during this preparation; its electrical details remain unverified here.

## Power connections

The external supply is rated **12 V DC / 5 A**. The ESP32 board is powered
through its **5V and GND pins**, rather than USB for standalone operation.
The 5 A rating is the supply's available current, not the board's consumption.

**Never connect the 12 V output directly to the board's 5V pin.** If the board
shares the 12 V supply, a suitable regulated 12 V-to-5 V converter is required.
Whether the current 5 V rail comes from a converter or a separate supply has
not yet been confirmed; record that device and its wiring before finalizing the
power diagram. Probe and RS485 converter power connections also need to be
recorded against their actual models.

Before connecting USB for flashing while external 5 V is present, verify the
board's power-selection/backfeed protection; otherwise disconnect external board
power for USB debugging. Switch power off before changing wiring.

## Candidate SEN0681 protocol

Checked against the [manufacturer protocol](https://wiki.dfrobot.com/sen0681/docs/21674)
on 2026-11-04. These settings apply only if the installed probe is SEN0681 and
its address/baud settings have not been changed.

- Modbus RTU, factory address `1`, default `4800` baud, `8N1`.
- Read six registers starting at `0x0000`, function `0x03`.
- Request: `01 03 00 00 00 06 C5 C8`.
- Decode three big-endian IEEE-754 float32 values: saturation ratio, DO in
  mg/L, and temperature in °C. Multiply the saturation ratio by 100 for percent.
- Validate response address, function, length, and CRC before decoding; reject
  non-finite values. Preserve error responses and raw bytes.

The sensor's salinity and atmospheric-pressure registers are compensation
settings, not independent measurements. Read and record them during setup;
do not present their configured values as measured EC/salinity/pressure. Verify
calibration and compensation for the actual water before treating readings as
analytically validated. Initial monitoring firmware should not silently write
calibration or compensation registers.

## Program files

- `firmware/node_01_do/node_01_do.ino`: sensor polling, USB diagnostics, Wi-Fi,
  NTP timestamps, and optional authenticated MQTT publishing.
- `firmware/node_01_do/Protocol.h`: response validation and decoding.
- `firmware/node_01_do/SerialLog.h`: bounded serial logging.
- `firmware/node_01_do/arduino_secrets.example.h`: public configuration template.
- `firmware/node_01_do/arduino_secrets.h`: local credentials, ignored by Git.
- `tests/protocol_test.cpp`: manufacturer-example decoding and malformed-frame tests.
- `../../web/`: the separate dashboard folder; frontend implementation is pending.

The local Wi-Fi configuration has been prepared on the development Mac. Do not
paste credentials into this README. On another computer, copy the example header
and fill it locally. The `.h` filename and sketch folder name must stay unchanged.

## Firmware behavior and limits

- Identity `node_01`; firmware source `0.1.3`; UART1 RX=18, TX=17.
- Polls approximately every 5 seconds, with a 1-second response timeout. MQTT
  connection attempts can delay polling; this is not a hard real-time schedule.
  Polling frequency is not the probe's physical response time.
- Outputs one JSON measurement per poll and a diagnostic status line every
  10 seconds. The node continues without an attached USB host.
- Uses DHCP. The status line reports the station MAC/IP for router reservation.
- Wi-Fi and MQTT reconnect automatically; blank broker configuration disables
  MQTT while USB sensor diagnostics and Wi-Fi remain active.
- NTP uses the configurable server. Before synchronization, `sample_time_utc`
  is `null` and `clock_status` is `UNSYNCED`; `uptime_ms` is always provided.
- Valid frames report DO, temperature, and saturation. Invalid frames report
  null measurements and an explicit `sensor_status`; raw bytes are preserved
  up to 64 bytes, with `raw_truncated` for overflow.
- `sensor_status=OK` means protocol/range checks passed, not calibration approval.
  Calibration and compensation remain `UNVERIFIED`; the program performs no
  sensor calibration/configuration writes.
- **No offline storage or retransmission queue in this first bench version.**
  Measurements that cannot be published increment `not_forwarded`. The JSON
  counter describes previous samples. All counters reset on reboot; boot ID
  and sequence identify each boot's records. USB output is best-effort and can
  be skipped/truncated if the host does not read it; `serial_skipped` counts this.
- MQTT uses QoS 1 and non-retained telemetry. Broker acknowledgement is not
  database acknowledgement. A receiver must deduplicate `(node_id, boot_id,
  sequence)`, save receive time, and detect gaps. Durable buffering comes before
  unattended research recording.

## 1. Check the hardware before powering the probe

Use only Node 01 during the first upload. Confirm the board label, sensor SKU,
converter variant, and supply ratings. The DO probe requires its own suitable
supply; a USB-powered ESP32 does not power the probe through RS485.

The SEN0681 manufacturer lists DC 10–30 V input and identifies brown as supply
positive, black as supply ground, yellow as RS485 A, and blue as RS485 B. Check
actual cable labels against the [sensor page](https://wiki.dfrobot.com/sen0681).
Do not apply that color mapping to a different probe.

Reference logic-side mapping from the earlier project (verify your converter's
terminal direction and 3.3 V compatibility before connecting):

| ESP32 | Converter TTL side |
| --- | --- |
| GPIO17 / TX | RXD |
| GPIO18 / RX | TXD |
| 3V3 | VCC, only for the verified compatible converter |
| GND | TTL-side GND |

Connect probe A/B only to the converter's RS485 side. The converter's isolated
reference/SGND arrangement must follow its manual; it is not approved by this
reference table. Disconnect power before changing wiring. Firmware preparation
and compilation do not certify the physical installation.

## 2. Open a Mac terminal and set paths

Run from the repository root. These commands use the Arduino CLI already bundled
with Arduino IDE on this Mac, so no separate CLI installation is needed.

```bash
cd /Users/lihongyang/Documents/clam_factory_deployment
ARDUINO_CLI="/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli"
CLAM_SKETCH="monitoring_nodes/node_01/firmware/node_01_do"
CLAM_FQBN="esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc,UploadSpeed=115200"
"$ARDUINO_CLI" version
"$ARDUINO_CLI" core list
```

The build targets 16 MB flash and OPI PSRAM. Native USB CDC remains enabled,
but application diagnostics explicitly use UART0 (`Serial0`). These
settings are for the reference N16R8 board, not every ESP32-S3 variant. The
Arduino core's default application partition is retained; no full-chip erase
is part of these instructions.

ESP32 core `3.3.11` and MQTT library `2.5.2` are installed on this Mac. On a
fresh machine, install them first:

```bash
"$ARDUINO_CLI" core update-index --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
"$ARDUINO_CLI" core install esp32:esp32@3.3.11 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
"$ARDUINO_CLI" lib install MQTT@2.5.2
```

## 3. Compile before uploading

```bash
"$ARDUINO_CLI" compile --fqbn "$CLAM_FQBN" --build-path build/node_01/arduino "$CLAM_SKETCH"
```

A successful compile ends with program and memory usage. Do not continue to
upload if compilation fails. The local configuration is compiled into firmware;
keep `build/` private as well as the credentials header.

Optional host-side protocol checks (requires Xcode command-line tools):

```bash
mkdir -p build/node_01
clang++ -std=c++11 -Wall -Wextra -Werror monitoring_nodes/node_01/tests/protocol_test.cpp -o build/node_01/protocol_test
./build/node_01/protocol_test
clang++ -std=c++11 -Wall -Wextra -Werror monitoring_nodes/node_01/tests/serial_log_test.cpp -o build/node_01/serial_log_test
./build/node_01/serial_log_test
```

## 4. Identify the USB port

Connect only the intended Node 01 using a USB data cable to its USB-to-UART
bridge connector. v0.1.3 logs use UART0; the native USB connector is not the
application console. The observed bridge has VID:PID `1A86:55D3` (WCH).
Close Arduino IDE's Serial Monitor before using CLI upload/monitor.

```bash
"$ARDUINO_CLI" board list
```

Compare the list with the board unplugged and plugged in. Use the actual newly appearing port. A `/dev/cu.usbmodem...` name alone does
not distinguish a USB-to-UART bridge from native ESP32 USB. Do not select
Bluetooth or the Mac debug-console port. An unidentified board name in the list
is possible; the explicit FQBN controls compilation/upload.

## 5. Upload manually

Set the port to your observed value, replacing the placeholder below:

```bash
CLAM_PORT="/dev/cu.usbmodem_REPLACE_WITH_ACTUAL_PORT"
"$ARDUINO_CLI" upload --port "$CLAM_PORT" --fqbn "$CLAM_FQBN" --input-dir build/node_01/arduino "$CLAM_SKETCH"
```

This replaces the selected board's application. Preserve any firmware you need
before uploading; no automatic backup is provided here. Recompile after editing
configuration or source, because this command uploads the existing build.

If it cannot connect, verify the cable/port, then hold BOOT, press and release
RESET, and release BOOT. List ports again and retry with the newly observed port.
After upload, press RESET if necessary and list ports again: the application
port can differ from the bootloader port. Do not run a full-chip erase to fix
an unexplained failure.

## 6. Monitor and reserve the IP

Update `CLAM_PORT` if the port changed, then run:

```bash
"$ARDUINO_CLI" monitor --port "$CLAM_PORT" --config baudrate=115200 --config dtr=on --config rts=off
```

Wait at least 10 seconds for a status line. Look for:

- `node=node_01`, `wifi=CONNECTED`, a station MAC, and a nonzero local IP.
- JSON with `sensor_status=OK` and real `do_mg_l`, `temperature_c`, and
  `saturation_pct` values. Confirm readings physically, not just their format.
- `mqtt=DISABLED` is expected until the gateway is configured.
- `clock_status=UNSYNCED` means NTP has not succeeded, not sensor failure.

Use the reported station MAC to find the router lease. Set **Make Static** to
Node 01's agreed, unused address; restart/renew and verify it took effect. Do not
enter the example IP from the top-level README without checking the real subnet.
Record the assignment in `commissioning.local.md` (ignored by Git).

For `TIMEOUT`, verify probe power, A/B, TTL TX/RX, address, and baud. For
`CRC_ERROR` or `SHORT_FRAME`, inspect wiring/noise and serial settings. An
`OUT_OF_RANGE` response stays in raw data but is not plotted as a valid reading.
If no USB output appears, verify the USB-to-UART connector and application port.
Use Ctrl+C to exit the monitor before uploading again.

## 7. Enable MQTT when the Jetson is ready

DO reading and Wi-Fi already work; no new sensor code is needed to enable
publishing. The web backend is not required for an initial MQTT subscriber test.

First complete the [Jetson broker setup](../../gateway/README.md): listener
`192.168.88.250:1883`, password file, and ACL. An active Mosquitto service alone
does not confirm LAN access or account configuration.

In the Mac's ignored `firmware/node_01_do/arduino_secrets.h`, set:

```cpp
constexpr char MQTT_HOST[] = "192.168.88.250";
constexpr uint16_t MQTT_PORT = 1883;
constexpr char MQTT_USER[] = "clam_node_01";
constexpr char MQTT_PASSWORD[] = "YOUR_NODE_MQTT_PASSWORD";
```

Use the password created for `clam_node_01`, not the Wi-Fi password, Jetson
login password, or `clam_gateway` password. Keep it local; do not paste it into
chat or commit it. Preserve the existing Wi-Fi settings. All three MQTT string
settings must be nonempty; an empty password keeps publishing disabled.

Compile again (Step 3), then upload over the Mac's USB-to-UART port (Step 5).
Close the serial monitor before uploading. Afterward, confirm
`mqtt=CONNECTED` in serial status and matching JSON samples in the Jetson
subscriber described in the gateway guide. A Wi-Fi connection alone does not
confirm MQTT delivery.

| Setting | Value |
| --- | --- |
| MQTT telemetry topic | `clam/node_01/telemetry` |
| MQTT status topic | `clam/node_01/status` |
| Telemetry | JSON, QoS 1, not retained |
| Status | Retained online/offline; Last Will on unexpected disconnect |
| Client identity | Node prefix plus hardware identifier |
| Default transport | TCP port 1883, authenticated, unencrypted; isolated project LAN only |

The receiver must also calculate data age; a retained online status alone does
not prove fresh sensor data. Do not expose the broker to the campus/public
network. The backend will serve the separate `web/` frontend without putting
broker credentials in browser code.

## Verification record

2026-11-04, development Mac:

- Host protocol tests passed, including the manufacturer's sample, CRC failure,
  wrong address, malformed length, Modbus exception, non-finite and out-of-range values.
- Arduino CLI 1.5.1 + ESP32 core 3.3.11 + MQTT 2.5.2: N16R8 configuration compiled
  successfully; program 926,775 bytes (70% of the selected app partition), static
  globals 46,932 bytes (14%). This does not include all runtime allocations.
- Credentials header and build output are Git-ignored; local header is owner-only.
- Board listing showed no ESP32 USB port. Nothing was uploaded.

Software checks and hardware checks are separate. Record the compiler/core/library
versions and actual results after each step. The subsequent user upload log
confirms v0.1.0 flashing and hash checks. Calibrated sensing, LAN delivery, and
web display have not been verified. The v0.1.1 cleanup preserves telemetry fields
and validation; it removes redundant checks and formatting without new dependencies.
Protocol tests and the same N16R8 build passed for v0.1.1: program 925,083 bytes,
static globals 46,876 bytes. That build was not uploaded; v0.1.2 was subsequently uploaded, as described below.

Next hardware checks: real sensor reply, renewed IP confirmation,
standalone power, MQTT delivery, and recovery after Wi-Fi/node/gateway restart.

Sources: [DFRobot protocol](https://wiki.dfrobot.com/sen0681/docs/21674),
[DFRobot sensor specifications](https://wiki.dfrobot.com/sen0681),
[Arduino CLI](https://docs.arduino.cc/arduino-cli/installation/), and
[Arduino MQTT](https://github.com/256dpi/arduino-mqtt).

### Console routing correction — v0.1.3

The v0.1.2 user upload log passed hash checks, but monitoring still showed only
ROM/bootloader output. USB enumeration identified the monitored port as WCH
VID:PID `1A86:55D3`. With `CDCOnBoot=cdc`, Arduino's `Serial` maps to native
USB CDC, while the connected bridge carries UART0. The earlier connection-flag
change did not resolve this interface mismatch.

v0.1.3 explicitly uses `Serial0` for logs, retains the UART1 sensor interface,
and removes the native-USB-only TX timeout call. The whole-line capacity check
and TX buffer limit remain. BOOT, UART_READY, WIFI_STARTED, SETUP_DONE and
periodic STATUS markers now target the bridge. No change to Wi-Fi credentials,
MQTT configuration, probe wiring, or telemetry fields is required.

Close the monitor with Ctrl+C, upload the rebuilt firmware using Step 5, then
reopen the monitor at 115200 baud. Release BOOT and briefly press RESET if
necessary. `waiting for download` indicates bootloader download mode, not a
running application. A missing probe should report TIMEOUT. The subsequent v0.1.3 log confirms application output over the bridge.

### First runtime observation — v0.1.3

User-provided output confirms firmware v0.1.3, one boot ID, sequences 4–8 at
5-second uptime intervals, and two Wi-Fi CONNECTED status lines. Every observed
sensor reply timed out with empty raw bytes and null measurements. Clock status
remained UNSYNCED and MQTT DISABLED. The increasing not_forwarded counter is
expected with publishing disabled; it is not evidence of a Wi-Fi failure.

Initial boot text was interrupted/partial, but subsequent JSON and status lines
were readable. This short observation does not validate long-term serial
integrity, sensor accuracy, network recovery, or end-to-end storage. MAC/IP
assignments are recorded only in the ignored local commissioning notes.
