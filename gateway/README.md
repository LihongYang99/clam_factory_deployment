# Jetson MQTT gateway

Mosquitto listens on Jetson `192.168.88.250:1883`. Nodes 01, 02, and 05 have
delivered real telemetry to the deployed recorder, API, and dashboard. Calibration
and compensation remain unverified. Negative ACL and anonymous-access tests
remain pending. See [dashboard setup](../docs/dashboard_setup.md) for deployment
and validation, and the dated first-node checkpoint below for historical evidence.

## Node 05 conductivity integration

The gateway accepts schema 1 telemetry on `clam/node_05/telemetry` for the Atlas
`EZO-EC` UART circuit. Its only required measurement is `conductivity_us_cm` in
µS/cm: a finite, nonnegative number when `sensor_status=OK`, or `null` for sensor
errors. Zero is a valid reading. The API at `/api/node_05?minutes=15` (or `60`)
keeps its samples separate from Node 01 and Node 02. Optional `salinity_psu`
contains EZO-derived estimated salinity from 0–42 PSU. Older samples may omit it;
missing or out-of-range firmware output remains null, not a synthesized value.

The circuit does not measure water temperature. Optional
`compensation_temperature_c` records its compensation **setting**, not a probe
reading. It is preserved in the original telemetry but must not enter the water
temperature average. Node 05 is not yet part of the prediction-result contract.
Code support does not establish successful hardware commissioning or calibration.

After syncing the updated `gateway/` directory, create the Node 05 MQTT account
and install the updated ACL in a Jetson terminal:

```bash
sudo mosquitto_passwd /etc/mosquitto/clam.passwd clam_node_05
sudo chown root:mosquitto /etc/mosquitto/clam.passwd
sudo chmod 640 /etc/mosquitto/clam.passwd
sudo install -o root -g mosquitto -m 640 ~/clam_factory_deployment/gateway/mosquitto/clam.acl /etc/mosquitto/clam.acl
sudo systemctl restart mosquitto clam-gateway
```

Enter the new Node 05 account password at the prompt and in that node's ignored
firmware secrets file. Do not use `mosquitto_passwd -c`, which replaces the password
file. The ACL permits this account to publish only its own telemetry/status;
the gateway's existing wildcard subscription already covers Node 05.

## 1. Install on the Jetson

Run in the Jetson terminal or an SSH session from the Mac:
`ssh lihong@192.168.88.250`. See [SSH troubleshooting](../docs/network_setup.md#ssh-from-the-mac-pitfalls-from-commissioning)
for username and DHCP pitfalls.

```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
mosquitto -h
sudo systemctl status mosquitto --no-pager
```

These instructions target Ubuntu 22.04's Mosquitto 2.x. Before changing an
existing installation, inspect `/etc/mosquitto/mosquitto.conf` and
`/etc/mosquitto/conf.d/` for other listeners, authentication, or existing projects.
Do not replace a shared broker configuration without reconciling it.

## 2. Create the first-node and receiver accounts (Jetson)

Use separate, new passwords. Enter them at the prompts; do not put passwords in
Git, screenshots, or chat. The node password must also go in its local firmware
configuration. The gateway password is for the receiver only.

```bash
sudo touch /etc/mosquitto/clam.passwd
sudo mosquitto_passwd /etc/mosquitto/clam.passwd clam_node_01
sudo mosquitto_passwd /etc/mosquitto/clam.passwd clam_gateway
sudo chown root:mosquitto /etc/mosquitto/clam.passwd
sudo chmod 640 /etc/mosquitto/clam.passwd
```

No `-c` flag is used: it would overwrite an existing password file. Add Node 02
using its [commissioning guide](../monitoring_nodes/node_02/README.md) and Node 05
using the integration section above. Each board needs its own broker account.

## 3. Install configuration (Jetson)

### A. Transfer the files from the Mac

Run in a **local Mac terminal**, not inside SSH:

```bash
scp /Users/lihongyang/Documents/clam_factory_deployment/gateway/mosquitto/clam.conf \
    /Users/lihongyang/Documents/clam_factory_deployment/gateway/mosquitto/clam.acl \
    lihong@192.168.88.250:~/
```

`scp` copies the two local files over SSH into the Jetson user's home directory
(`/home/lihong`). It uses the Jetson login password. This only stages the files;
it does not yet change the running broker or copy MQTT passwords.

### B. Activate the configuration on the Jetson

Run in the **Jetson SSH terminal**:

```bash
sudo install -o root -g mosquitto -m 640 ~/clam.acl /etc/mosquitto/clam.acl
sudo install -o root -g root -m 644 ~/clam.conf /etc/mosquitto/conf.d/clam.conf
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
sudo systemctl status mosquitto --no-pager
sudo ss -ltnp 'sport = :1883'
```

Here, `install` means copy a configuration file into its system location and
set ownership/permissions; it does not install another software package.
`-o` sets the owner, `-g` the group, and `-m` the permission mode. Mode `640`
allows the owner to read/write and the group to read; `644` also allows others
to read. The ACL is readable by the `mosquitto` service group.

| File or command | Purpose |
| --- | --- |
| `clam.conf` | Listen on the Jetson LAN address, reject anonymous clients, and load the password and ACL files |
| `clam.acl` | Allow each of `clam_node_01`, `clam_node_02`, and `clam_node_05` to publish only its own telemetry/status; allow `clam_gateway` to read node telemetry/status |
| `/etc/mosquitto/clam.passwd` | Previously created MQTT password hashes; neither transferred file contains these passwords |
| `systemctl enable mosquitto` | Start the broker automatically at boot |
| `systemctl restart mosquitto` | Restart the broker so it reads the new configuration; temporarily disconnect existing clients |
| `systemctl status mosquitto` | Check whether the broker process is running |
| `ss -ltnp 'sport = :1883'` | Show TCP listening sockets on port 1883, with numeric addresses and owning processes |

Before configuration, the observed listeners were `127.0.0.1:1883` and
`[::1]:1883`, which accept connections only from the Jetson itself. Afterward,
the observed listener was `192.168.88.250:1883`, allowing LAN clients to attempt
connections. This does not by itself prove a successful login or sensor delivery;
verify those in Step 5. This step changes the broker, not the ESP32 firmware.

Expected listener: `192.168.88.250:1883`. This deliberately does not listen on
Jetson's campus-network address. If startup fails:

```bash
sudo journalctl -u mosquitto -n 50 --no-pager
```

If UFW is already active, allow the sensor LAN without disabling the firewall:

```bash
sudo ufw status
sudo ufw allow from 192.168.88.0/24 to 192.168.88.250 port 1883 proto tcp
```

This is authenticated, unencrypted MQTT for the trusted bench LAN. Do not expose
port 1883 through router port forwarding; use TLS before use on an untrusted network.

## 4. Enable Node 01 publishing (Mac)

Edit only the ignored file
`monitoring_nodes/node_01/firmware/node_01_do/arduino_secrets.h`:

```cpp
constexpr char MQTT_HOST[] = "192.168.88.250";
constexpr uint16_t MQTT_PORT = 1883;
constexpr char MQTT_USER[] = "clam_node_01";
constexpr char MQTT_PASSWORD[] = "YOUR_NODE_ACCOUNT_PASSWORD";
```

Keep the existing Wi-Fi settings. Use the actual node account password locally.
Then **compile and upload again** using the [Node 01 guide](../monitoring_nodes/node_01/README.md).
Unlike changing a DHCP reservation, changing credentials compiled into firmware
requires reflashing. Close the serial monitor before uploading.

## 5. Observe actual telemetry (Jetson, Bash terminal)

```bash
read -r -s -p 'Gateway MQTT password: ' CLAM_MQTT_PASSWORD
printf '\n'
mosquitto_sub -h 192.168.88.250 -p 1883 \
  -u clam_gateway -P "$CLAM_MQTT_PASSWORD" \
  -t 'clam/+/telemetry' -t 'clam/+/status' -q 1 -v
unset CLAM_MQTT_PASSWORD
```

Use Ctrl+C to stop the subscriber. Password input is hidden and not stored in
shell history; the expanded password can be visible in process arguments while
this commissioning command runs. Use only on the trusted Jetson account.

Verify all of the following:

- ESP32 serial status reports `mqtt=CONNECTED` and `ip=192.168.88.101`.
- Subscriber receives `clam/node_01/telemetry` about every five seconds.
- Sequence, boot ID, DO, and temperature match the USB JSON for the same sample.
- Anonymous connections are rejected: running the same subscriber without
  `-u` and `-P` must report an authorization failure.

`clock_status=UNSYNCED` remains a separate clock issue. A successful MQTT receipt
is not proof of database storage: `mosquitto_sub` only displays messages. The
separate gateway service records and serves them; verify it using
[dashboard setup](../docs/dashboard_setup.md).

References: [Mosquitto authentication](https://mosquitto.org/documentation/authentication-methods/)
and [password utility](https://www.mosquitto.org/man/mosquitto_passwd-1.html).

## Verified Node 01 reception — 2026-11-06

The owner supplied two messages received by `mosquitto_sub` on the Jetson topic
`clam/node_01/telemetry`, using the gateway account. Sequences 33 and 34 had
uptimes 161002 and 166002 ms. DO was 6.1542 and 6.1494 mg/L; temperature was
25.3423 and 25.3202 °C. Both reported `sensor_status=OK`.

`not_forwarded_before_sample` stayed at 27: this is the accumulated count of
earlier failed forwarding attempts, not 27 new failures per message. There is
no offline replay queue. Two received messages verify the current acquisition
and MQTT path at that checkpoint, not long-term reliability. Those samples had
null/UNSYNCED sample UTC and UNVERIFIED calibration/compensation. No database
recorder or dashboard was running at that time; both were deployed afterward.
