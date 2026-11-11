# Node 05 — electrical conductivity

Atlas Scientific EZO-EC over UART, with a physical **K10 probe confirmed by the
operator**. Read-only identification confirmed an **ESP32-S3 v0.2 with 16 MB
flash and embedded 8 MB PSRAM**, MAC `44:1B:F6:FE:71:50`. Firmware `0.1.0` was
compiled and uploaded with flash-hash verification. UART wiring confirmation, the circuit's stored K
value, calibration, and live delivery remain pending. No EC response has yet
been verified, and no calibration has been performed for this deployment.

Local validation passed the UART parser checks, nine gateway tests, and the
dashboard browser checks at 1440, 900, and 390 px widths. These checks use test
fixtures; they do not establish live EC delivery.

## Wiring and acquisition

The reference setup uses an Atlas ISCCB-2 carrier with a 3.3 V host interface.
Confirm the installed carrier and these connections before operating the probe;
disconnect power before changing wiring.

| ESP32 connection | Carrier connection |
| --- | --- |
| GPIO17 / UART TX | RX |
| GPIO18 / UART RX | TX |
| 3.3 V | Host-side VCC |
| GND | Host-side GND |

This is TTL UART at **9600 baud, 8N1**, not RS485. USB diagnostics use **115200
baud**. The firmware requests one `R` reading every five seconds in normal
operation. EZO commands and responses end with carriage return (`0x0D`); a
reading normally takes 600 ms. The firmware allows 1800 ms per transaction and
requires the numeric response plus `*OK`.

Initialization disables continuous output, enables acknowledgements, queries
`i`, `K,?`, `T,?`, and `Cal,?`, then enables EC output and disables TDS, salinity,
and specific gravity. It never writes a K value, temperature compensation, or
calibration. If the stored K differs from 10, `CONFIG_MISMATCH` keeps conductivity
null. Resolve that mismatch deliberately before using measurements; do not
assume that changing K preserves the validity of an earlier calibration.

Telemetry uses `clam/node_05/telemetry` and `clam/node_05/status`:

| Field | Meaning |
| --- | --- |
| `conductivity_us_cm` | Conductivity in µS/cm; null on failure; a valid zero remains zero |
| `probe_k` | K value queried from the EZO circuit |
| `compensation_temperature_c` | Queried compensation setting, **not measured water temperature** |
| `calibration_status`, `compensation_status` | `UNVERIFIED` in this firmware |

`sensor_status=OK` confirms acquisition and parsing, not calibration accuracy.
Unsynchronized sample time remains null. There is no offline queue;
`not_forwarded_before_sample` counts samples not forwarded, including while
MQTT is disabled.

## 1. Identify the board on the Mac

Close other serial monitors. Read-only flash identification succeeded on
`/dev/cu.usbmodem1301` after BOOT/RESET; the earlier port was
`/dev/cu.usbmodem1234561`. Check again because USB enumeration can change.
To enter download mode, hold BOOT, press/release RESET, then release BOOT.

```bash
cd /Users/lihongyang/Documents/clam_factory_deployment
ls /dev/cu.*
CLAM_PORT=/dev/cu.usbmodem1301
CLAM_ESPTOOL="$HOME/Library/Arduino15/packages/esp32/tools/esptool_py/5.3.1/esptool"
"$CLAM_ESPTOOL" --port "$CLAM_PORT" --before no-reset --after no-reset flash-id
```

The build settings below match this identified **ESP32-S3 N16R8** board.
For a replacement board, check its reported chip, flash, and PSRAM before
reusing these settings; flash capacity alone does not establish PSRAM capacity.

## 2. Configure and compile

Keep the existing ignored `firmware/node_05_ec/arduino_secrets.h`; the local
Wi-Fi settings are already prepared. For a new checkout, copy the example only
if the local file is absent, then fill the Wi-Fi credentials:

```bash
CLAM_SKETCH="monitoring_nodes/node_05/firmware/node_05_ec"
test -f "$CLAM_SKETCH/arduino_secrets.h" || cp "$CLAM_SKETCH/arduino_secrets.example.h" "$CLAM_SKETCH/arduino_secrets.h"
ARDUINO_CLI="/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli"
CLAM_FQBN="esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,USBMode=hwcdc,CDCOnBoot=cdc,UploadSpeed=115200"
"$ARDUINO_CLI" compile --fqbn "$CLAM_FQBN" --build-path build/node_05/arduino "$CLAM_SKETCH"
```

This uses the existing ESP32 core 3.3.11 and MQTT library 2.5.2; installation
commands are in the [Node 01 guide](../node_01/README.md). The empty
`MQTT_PASSWORD` keeps MQTT disabled for the initial USB check. Do not overwrite
the local credentials file or reuse another node's MQTT account.

Optional host protocol check, with no attached device required:

```bash
c++ -std=c++11 -Wall -Wextra -Werror monitoring_nodes/node_05/tests/protocol_test.cpp -o /tmp/clam-node05-protocol-test
/tmp/clam-node05-protocol-test
```

## 3. Upload and inspect USB output

Continue only after a successful build and board identification. Recheck the
port, then upload in the same Mac terminal:

```bash
"$ARDUINO_CLI" upload --port "$CLAM_PORT" --fqbn "$CLAM_FQBN" --input-dir build/node_05/arduino "$CLAM_SKETCH"
"$ARDUINO_CLI" monitor --port "$CLAM_PORT" --config baudrate=115200 --config dtr=on --config rts=off
```

If needed, press RESET once without BOOT to start the application. Expect
`node_05`, firmware `0.1.0`, and `event=EC_CONFIG` showing the queried K,
compensation setting, and calibration mode. For K10, initialization should reach
`event=EC_READY`; subsequent JSON should contain actual conductivity and
`sensor_status=OK`. A timeout, wrong sensor, or configuration error must remain
visible with null conductivity. Record the exact diagnostic before changing
settings. No calibration command interface is included.

Check `event=STATUS` for the current station MAC, DHCP IP, and Wi-Fi connection.
`mqtt=DISABLED` is expected until the account is configured. `clock_status`
becomes `SYNCED` only after a successful NTP response from `192.168.88.250`.

## 4. Enable MQTT and the dashboard

The existing broker is `192.168.88.250:1883`. First sync the gateway, dashboard,
and ACL from the **Mac**, preserving the Jetson's private `.env`:

```bash
rsync -av --exclude='.env' --exclude='__pycache__/' gateway web lihong@192.168.88.250:~/clam_factory_deployment/
ssh lihong@192.168.88.250
```

Now run on the **Jetson**. Add the dedicated account to the existing password
file; do **not** add `-c`, which would replace the file and its other accounts.
The `mosquitto_passwd` prompt sets the Node 05 MQTT password, separately from
the Jetson login password requested by `sudo`.

```bash
cd ~/clam_factory_deployment
sudo mosquitto_passwd /etc/mosquitto/clam.passwd clam_node_05
sudo chown root:mosquitto /etc/mosquitto/clam.passwd
sudo chmod 640 /etc/mosquitto/clam.passwd
sudo install -o root -g mosquitto -m 640 gateway/mosquitto/clam.acl /etc/mosquitto/clam.acl
sudo systemctl restart mosquitto clam-gateway
systemctl is-active mosquitto clam-gateway
```

The ACL permits `clam_node_05` to publish only its telemetry/status topics; the
existing `clam_gateway` wildcard subscription already covers Node 05. Keep the
existing gateway credentials and database. See [gateway setup](../../gateway/README.md)
if these services have not yet been installed.

Back on the Mac, enter the new password in the ignored Node 05 secrets file.
Keep `MQTT_HOST="192.168.88.250"`, `MQTT_USER="clam_node_05"`, and port 1883.
Recompile/upload, then confirm `mqtt=CONNECTED`. A connected status alone does
not establish successful storage.

## 5. Reserve the IP and verify the complete path

Reserve **192.168.88.105** after matching the station MAC printed by this board
to the identified MAC `44:1B:F6:FE:71:50`. The reservation is not yet verified.
Follow [LAN reservations](../../docs/network_setup.md):
WebFig → IP → DHCP Server → Leases, match the MAC, check that `.105` is available,
Make Static, set Address, and save. Reset the board without BOOT and verify both
Address and Active Address are `.105`. Firmware stays on DHCP.

On the Jetson, inspect two actual MQTT messages using the existing gateway
account (the password prompt below is Bash syntax):

```bash
read -r -s -p 'Gateway MQTT password: ' CLAM_MQTT_PASSWORD
printf '\n'
mosquitto_sub -h 192.168.88.250 -p 1883 -u clam_gateway -P "$CLAM_MQTT_PASSWORD" -t 'clam/node_05/telemetry' -q 1 -C 2 -v
unset CLAM_MQTT_PASSWORD
```

From the Mac or Jetson:

```bash
curl --fail --silent --show-error 'http://192.168.88.250:8000/api/node_05?minutes=15'
```

Compare USB, MQTT, API, and the conductivity detail view on the
[dashboard](http://192.168.88.250:8000). Check real values, units, sequence, sample
time, receive time, and error states. The compensation setting must never enter
the water-temperature chart or average. Check that disconnecting the node
produces stale/offline information and chart gaps, then verify recovery.

Record board identity, MAC/IP, firmware, configured K, calibration mode, and
observed results before marking commissioning complete. Calibration against
appropriate standards remains a separate task.

## References

- [Atlas EZO-EC datasheet](https://files.atlas-scientific.com/EC_EZO_Datasheet.pdf):
  UART, output units, K/temperature queries, and calibration procedure.
- [Atlas K10 probe](https://atlas-scientific.com/probes/conductivity-probe-k-10/):
  probe specifications; no internal temperature sensor.
- [Atlas isolated carrier](https://files.atlas-scientific.com/Isccb.pdf):
  verify the installed carrier and its connections.
