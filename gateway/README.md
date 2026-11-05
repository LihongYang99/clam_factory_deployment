# Jetson MQTT gateway

First milestone: receive Node 01 telemetry on Jetson `192.168.88.250`.
The broker configuration is prepared; installation and delivery are not yet
verified on the Jetson. Storage, API, and dashboard implementation follow this step.

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

## 2. Create accounts (Jetson)

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

No `-c` flag is used: it would overwrite an existing password file.

## 3. Install configuration (Jetson)

Copy this repository's `gateway/mosquitto/` directory to the Jetson first; these
files may not yet exist in the remote GitHub repository. From that directory:

```bash
sudo install -o root -g mosquitto -m 640 clam.acl /etc/mosquitto/clam.acl
sudo install -o root -g root -m 644 clam.conf /etc/mosquitto/conf.d/clam.conf
sudo systemctl enable mosquitto
sudo systemctl restart mosquitto
sudo systemctl status mosquitto --no-pager
sudo ss -ltnp 'sport = :1883'
```

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
is not database storage; this milestone does not yet save telemetry or serve a page.

References: [Mosquitto authentication](https://mosquitto.org/documentation/authentication-methods/)
and [password utility](https://www.mosquitto.org/man/mosquitto_passwd-1.html).
