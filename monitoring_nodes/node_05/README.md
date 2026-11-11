# Node 05 — electrical conductivity

Atlas Scientific EZO-EC over UART, with a physical **K10 probe confirmed by the
operator**. Read-only identification confirmed an **ESP32-S3 v0.2 with 16 MB
flash and embedded 8 MB PSRAM**, MAC `44:1B:F6:FE:71:50`. Firmware `0.1.3` adds
explicit USB calibration commands. UART acquisition,
Wi-Fi at temporary DHCP address `192.168.88.97`, and NTP synchronization are verified.
MQTT is still disabled; broker delivery and the `.105` reservation remain pending.
The 0.1.3 host tests and ESP32 build passed; upload hashes and the on-device
version were verified. `CAL BEGIN` and `CAL STATUS` responded correctly, with
USB readings continuing while the forwarding counter remained unchanged.
The dry, 12,880 µS/cm low, and 150,000 µS/cm high writes each returned `*OK`
on November 11, 2026. After the high write, `Cal,?` returned 2 and the firmware
advanced to `next=VERIFY`; a separate status query confirmed the same result.
Readings in the calibration cup were 148,900–149,400 µS/cm for about one minute.
This confirms the acknowledged sequence and its immediate response, not an
independent accuracy check. The first fresh low-standard recheck, reported at
22°C, settled near 15,500 µS/cm, about 20% above the bottle's nominal 12,880.
This comparison is not temperature-corrected and does not verify accuracy.
A second fresh low aliquot in another clean cup after thorough rinsing instead
settled at 11,190–11,210 µS/cm for about 95 seconds, with all responses OK and
no setting changes. The operator confirmed this replacement aliquot was also
approximately 22°C. The first result was not reproduced; neither carryover nor
another cause is established. Accuracy has not been verified.
Plan one controlled repeat of the complete dry/low/high sequence with connections
unchanged and, if practical, both standards stabilized at their 25°C reference
temperature. This temperature choice simplifies verification; it is not a claim
that Atlas prohibits calibration at 22°C. Preparation and the repeat are pending.
Calibration and compensation status remain `UNVERIFIED`.

The circuit initially reported K=1 and calibration mode 0; firmware configured
the confirmed physical K10 probe and read the setting back. Current settings
are K10, compensation 25°C, and calibration mode 2. The last queried EZO-side
supply was 3.87 V; this is the isolated sensor rail, not the host supply.

Earlier checks included intermittent near-zero readings and manipulation of the
**SMA threaded probe connector**. Before the high write, the low-standard response
shifted from approximately 11,400 to 12,530–12,570 µS/cm without another low write;
the cause remains unresolved. Fresh high standard subsequently gave a continuous
nonzero response and settled near 95,000 µS/cm before its single calibration
write. Keep connections unchanged for the independent rechecks. If they fail,
resolve the measurement inconsistency and repeat the full physical procedure.

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
`i`, `Status`, `K,?`, `T,?`, and `Cal,?`, then enables EC output and disables TDS, salinity,
and specific gravity. Firmware 0.1.1 matches the confirmed physical K10 probe:
if K differs from 10 and `Cal,?` reports mode 0, it sends `K,10` and requires
acknowledged K=10 readback. It attempts that write at most once per boot; an
uncertain result is followed by fresh queries, not repeated writes. A mismatch
with existing calibration mode 1 or 2 remains `CONFIG_MISMATCH` with null EC.
It does not write temperature compensation. Calibration writes occur only after
explicit USB commands in calibration mode, as described below. Setting the probe
type does not establish measurement accuracy; calibration stays UNVERIFIED.

Telemetry uses `clam/node_05/telemetry` and `clam/node_05/status`:

| Field | Meaning |
| --- | --- |
| `conductivity_us_cm` | Conductivity in µS/cm; null on failure; a valid zero remains zero |
| `probe_k` | K value queried from the EZO circuit |
| `compensation_temperature_c` | Queried compensation setting, **not measured water temperature** |
| `calibration_status`, `compensation_status` | `UNVERIFIED` in this firmware |

`sensor_status=OK` confirms acquisition and parsing, not calibration accuracy.
Firmware 0.1.2 rejects EC above the K10 probe's documented 1 S/cm
(1,000,000 µS/cm) upper range as `OUT_OF_RANGE`, with null conductivity and the
raw response retained. Zero is preserved for diagnostics; it does not establish
a valid tap-water measurement. The circuit's separate `500,000+` specification
is not interpreted as an exact upper limit.
Unsynchronized sample time remains null. There is no offline queue;
`not_forwarded_before_sample` counts samples not forwarded, including while
MQTT is disabled.
Calibration mode pauses MQTT telemetry while USB readings continue; intentionally
paused readings do not increment this counter.

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
c++ -std=c++11 -Wall -Wextra -Werror monitoring_nodes/node_05/tests/calibration_test.cpp -o /tmp/clam-node05-calibration-test
/tmp/clam-node05-calibration-test
```

## 3. Upload and inspect USB output

Continue only after a successful build and board identification. Recheck the
port, then upload in the same Mac terminal:

```bash
"$ARDUINO_CLI" upload --port "$CLAM_PORT" --fqbn "$CLAM_FQBN" --input-dir build/node_05/arduino "$CLAM_SKETCH"
"$ARDUINO_CLI" monitor --port "$CLAM_PORT" --config baudrate=115200 --config dtr=on --config rts=off
```

If needed, press RESET once without BOOT to start the application. Expect
`node_05`, firmware `0.1.3`, and `event=EC_CONFIG` showing the queried K,
compensation setting, and calibration mode. For K10, initialization should reach
`event=EC_READY`; subsequent JSON should contain actual conductivity and
`sensor_status=OK`. A timeout, wrong sensor, or configuration error must remain
visible with null conductivity. Record the exact diagnostic before changing
settings. `EC_K_CONFIGURING` and `EC_K_CONFIRMED` identify the guarded K10 setup.

`event=EC_POWER response=?Status,P,3.300` is an example diagnostic, not a recorded
value: `Status` queries EZO-side supply voltage and the last restart reason
(`P` power cycle, `S` software reset, `B` brownout, `W` watchdog, `U` unknown).
It does not change calibration. A normal voltage does not prove probe continuity
or exclude intermittent power faults. If EC stays zero in water, preserve the
raw logs and inspect the carrier, EZO module, probe connector, and trapped air
before calibration. Disconnect power before reseating hardware.

Check `event=STATUS` for the current station MAC, DHCP IP, and Wi-Fi connection.
`mqtt=DISABLED` is expected until the account is configured. `clock_status`
becomes `SYNCED` only after a successful NTP response from `192.168.88.250`.

## Calibrate the K10 probe through USB

Use the [Atlas EZO-EC datasheet V6.7, pp. 66–71](https://files.atlas-scientific.com/EC_EZO_Datasheet.pdf).
This firmware supports the kit's **12,880 µS/cm low** and **150,000 µS/cm high**
standards. Use separate clean portions of undiluted solution, fully immerse the
sensing area, remove trapped bubbles, and wait for stable readings at each wet
point. Do not pour used solution back into its bottle.

Keep the EZO temperature-compensation setting at **25°C during calibration**.
This is a setting, not a water-temperature measurement. If a standard's actual
temperature is 5°C or more away from 25°C, stop: use its temperature-specific
conductivity from the bottle and adapt the commands before proceeding. The
fixed commands below do not support other target values.

Open the monitor from section 3 at 115200 baud. While it is running, type each
command below into that terminal and press **Return**. These commands go to the
ESP32; they are not macOS shell commands. If the `%` shell prompt is visible,
restart the monitor first. In Arduino IDE, select **Newline** as the line ending.
Do not paste the complete calibration sequence at once.

1. **Enter calibration mode.** Send `CAL BEGIN`, then `CAL STATUS`.
   Expect `mode=ON next=DRY`, `probe_k=10.00`, and
   `compensation_temperature_c=25.00`. MQTT telemetry pauses to keep standards
   out of the process history; USB readings and Wi-Fi continue.
2. **Dry point.** Rinse with DI water, shake off excess, and let the sensing end
   air-dry completely. Only when physically dry, send `CAL DRY CONFIRM`.
   Expect `command=Cal,dry result=ACK` and `next=LOW`. A nonzero reading before
   the dry command is possible; the expected reading after dry calibration is zero.
3. **Low point.** Put the dry probe into fresh 12,880 µS/cm standard. Wait until
   readings stabilize, then send `CAL LOW 12880 CONFIRM`.
   Expect `command=Cal,low,12880 result=ACK` and `next=HIGH`.
   **The low-point write does not immediately change readings.**
4. **High point.** Rinse with DI water and shake off excess. Immerse in fresh
   150,000 µS/cm standard and wait until stable. Send `CAL HIGH 150000 CONFIRM`.
   Expect `command=Cal,high,150000 result=ACK`, `next=VERIFY`, `cal_mode=2`,
   and `event=CAL_SEQUENCE_CONFIRMED`. The high point completes the correction.
5. **Recheck.** Keep calibration mode on. Check stable readings in fresh high
   standard, rinse, and check fresh low standard without sending further point
   commands. Record actual readings, solution temperatures, standards/lot numbers,
   and timestamps. Command acknowledgements and stored mode 2 establish the
   sequence, not the accuracy of these rechecks. The firmware therefore retains
   `calibration_status=UNVERIFIED`; it does not generate a verified date.
6. **Resume.** Rinse and return the probe to the process sample before sending
   `CAL END`. MQTT telemetry resumes. `CAL END` does not undo probe writes.

`CAL STATUS` is read-only. Repeating `CAL BEGIN` while already in mode preserves
progress. Sequence progress is in ESP32 RAM and is lost on reset or `CAL END`;
this does not imply that calibration stored inside the EZO was erased.
Neither boot nor `CAL BEGIN` writes calibration values or clears old points.

If a write returns `CAL_WRITE_UNCONFIRMED`, stop. The firmware blocks further
points and does not retry automatically; the probe may have received the write
even if its acknowledgement was lost. Retain the raw reply, resolve the fault,
then use `CAL END` / `CAL BEGIN` and repeat the full physical procedure if needed.
`CAL_SEQUENCE_NOT_CONFIRMED` after an acknowledged high point calls for a fresh
`CAL STATUS` query, not another high-point write. A zero reading in wet standard
is rejected. Readings outside Atlas's approximate ±40% pre-calibration guidance
produce a warning; that guidance is not an accuracy tolerance.

If independent standard checks disagree after the sequence, first confirm the
actual solution temperatures and fresh, undiluted standards. For a controlled
repeat, use `CAL END` / `CAL BEGIN` to restart the firmware sequence, then repeat
all physical steps; do not patch only the low point. Keep electrical connections
unchanged. If the controlled repeat still fails the standard checks, investigate
the standards and probe/circuit measurement path rather than repeatedly rewriting
calibration. Record discrepancies and leave accuracy unverified.

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
