# Run the recorder and dashboard

The gateway is one Python process: Paho subscribes to MQTT, SQLite stores the
original JSON and gateway receive time, and a read-only HTTP server serves `web/`.
No frontend build, Node.js, external fonts, or internet connection is needed at
runtime. Install Python dependencies once while internet access is available.

## 1. Copy from the Mac

In a **local Mac terminal**:

```bash
ssh lihong@192.168.88.250 'mkdir -p ~/clam_factory_deployment'
rsync -av --exclude='.env' --exclude='__pycache__/' \
  /Users/lihongyang/Documents/clam_factory_deployment/gateway \
  /Users/lihongyang/Documents/clam_factory_deployment/web \
  /Users/lihongyang/Documents/clam_factory_deployment/docs \
  /Users/lihongyang/Documents/clam_factory_deployment/README.md \
  lihong@192.168.88.250:~/clam_factory_deployment/
```

The transfer excludes `.env`; configure the gateway password on Jetson itself.
The ESP32 secrets file is outside these directories.
This copy does not reinstall Mosquitto configuration or overwrite the SQLite data
folder. Run one receiver instance only: its persistent MQTT client ID is
`clam-receiver`. Do not run a second instance on the Mac against the same broker.

For an existing deployment, restart the gateway after copying Python/API changes:

```bash
ssh -t lihong@192.168.88.250 'sudo systemctl restart clam-gateway && systemctl is-active clam-gateway'
```

Then refresh the browser. The Prediction dashboard needs the new
`/api/predictions` endpoint, so its first deployment must include both `gateway/`
and `web/`. Without a trained model it displays **Waiting for LSTM results**.
The [prediction results guide](predictions.md) defines the future 12-hour output
and hourly inference integration; no scheduled prediction job is enabled yet.

Node 05 EC also requires the updated gateway for `/api/node_05`, plus its MQTT
account and ACL. Follow [Node 05 commissioning](../monitoring_nodes/node_05/README.md)
before expecting real conductivity readings. Its compensation-temperature setting
is excluded from the water-temperature average.

## 2. Configure on the Jetson

In the **Jetson SSH terminal**:

```bash
cd ~/clam_factory_deployment
sudo apt install python3-venv
python3 -m venv .venv
.venv/bin/pip install -r gateway/requirements.txt
cp -n gateway/.env.example gateway/.env
chmod 600 gateway/.env
nano gateway/.env
```

Set `MQTT_PASSWORD` to the **clam_gateway MQTT password**. Keep passwords out of
chat and Git. Enter plain values after `=`, without surrounding quotes; the
minimal loader splits on the first `=`. Change `HTTP_HOST` to `192.168.88.250`
for viewing from the Jetson and other devices on the clam LAN. Keep
`MQTT_HOST=192.168.88.250` and `MQTT_USER=clam_gateway`.

Save with Ctrl+O, Enter, then Ctrl+X. Start:

```bash
.venv/bin/python gateway/app.py
```

Open **http://192.168.88.250:8000** in Chromium on the Jetson or a browser on
the Mac connected to the same LAN. This service is read-only but has no browser
login or TLS: use only on the trusted project LAN, with no public port forwarding.
If a firewall is enabled, allow port 8000 only from the project subnet.

## 3. Verify real recording

Keep Node 01 powered and connected. Expect `Telemetry subscription ready=True`
in the terminal and readings on the page within about 10 seconds. Confirm:

- DO/temperature and sequence match the Node 01 serial or MQTT subscriber output.
- SQLite row count increases; duplicate `(node_id, boot_id, sequence)` messages
  do not create extra rows.
- Stopping Node 01 causes `Telemetry stale` after 20 seconds without reception.
- Disconnecting the broker shows receiver disconnection; stored values remain
  labeled with their age. Restoring the broker reconnects automatically.
- Invalid sensor samples appear as missing values, not zero. Sequence gaps,
  reboot boundaries, invalid readings, and reception gaps over 20 seconds break
  the curve. The table exposes recent exact values.

Inspect the database in another Jetson SSH terminal:

```bash
cd ~/clam_factory_deployment
.venv/bin/python -c "import sqlite3; db=sqlite3.connect('data/telemetry.sqlite3'); print(db.execute('SELECT node_id, count(*) FROM samples GROUP BY node_id').fetchall()); db.close()"
```

History uses **gateway receive time**. Unsynchronized node sample times remain
null, and queued messages may arrive later than acquisition. Recent receipt is
not proof of a current sample or a continuously online sensor. Synchronize the
Jetson clock as well; clock changes affect receive-time charts.

## 4. Keep it running after SSH closes

After the foreground check passes, stop it with Ctrl+C, then install the service:

```bash
sudo install -m 644 gateway/clam-gateway.service /etc/systemd/system/clam-gateway.service
sudo systemctl daemon-reload
sudo systemctl enable --now clam-gateway
sudo systemctl status clam-gateway --no-pager
```

The service assumes user `lihong` and `/home/lihong/clam_factory_deployment`.
Adjust those paths if deploying elsewhere. View errors with:

```bash
sudo journalctl -u clam-gateway -n 50 --no-pager
```

Restart the service after changing `.env` or Python code. SQLite data remains in
`data/telemetry.sqlite3`. Do not copy only that file while recording: SQLite WAL
files may contain uncheckpointed data; stop the service before copying all data,
or use SQLite's backup API.

## Limits and checks

This is a bench LAN service using Python's standard HTTP server, not a hardened
public deployment. History is limited to 15 or 60 minutes and the latest 1,000
rows per request; the database retains all accepted records with no automatic
retention policy. Watch disk capacity before unattended recording.

MQTT QoS 1 acknowledgment is sent after a successful SQLite commit. Invalid
payloads and retained telemetry are rejected/ignored and acknowledged. A write
failure is reported without acknowledging the message; repair storage and
restart the receiver. MQTT persistence is not a replacement for backups, and
the ESP32 has no offline sample queue. Calibration/compensation are still unverified.

Local checks:

```bash
python3 -m unittest discover -s gateway/tests -v
```

Current validation: nine storage/API tests passed. On November 11, 2026, the
updated gateway was deployed to Jetson and actual Node 05 EC samples were
verified through USB, MQTT delivery, SQLite, the API, and Chrome's overview and
conductivity detail page. Node 01 and Node 02 continued reporting. Calibration
and compensation remain `UNVERIFIED`; conductivity values near zero are shown
as received, not presented as verified water measurements.
