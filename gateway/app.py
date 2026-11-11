"""Local monitoring gateway: MQTT -> SQLite -> read-only HTTP dashboard."""
import json
from contextlib import contextmanager
import logging
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
LOG = logging.getLogger('clam')
STATUS = {'mqtt_connected': False, 'subscription_ready': False, 'storage_error': False}
STATUS_LOCK = threading.Lock()


def health(**changes):
    with STATUS_LOCK:
        STATUS.update(changes)
        return dict(STATUS)


def load_env(path):
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())


def validate(topic, payload):
    if len(payload) > 8192:
        raise ValueError('payload too large')
    def reject_constant(value):
        raise ValueError("non-finite JSON number")
    data = json.loads(payload, parse_constant=reject_constant)
    if not isinstance(data, dict):
        raise ValueError('expected object')
    node = data.get('node_id')
    if not isinstance(node, str) or not re.fullmatch(r'node_\d{2}', node):
        raise ValueError('invalid node id')
    if topic != f'clam/{node}/telemetry' or type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ValueError('topic or schema mismatch')
    if not isinstance(data.get('boot_id'), str) or not re.fullmatch(r'[0-9a-fA-F]{16}', data['boot_id']):
        raise ValueError('invalid boot id')
    for key in ('sequence', 'uptime_ms', 'not_forwarded_before_sample'):
        value = data.get(key)
        if type(value) is not int or not 0 <= value < 2**63:
            raise ValueError('invalid counter')
    for key in ('sensor_status', 'clock_status', 'calibration_status', 'compensation_status'):
        if not isinstance(data.get(key), str) or not re.fullmatch(r'[A-Z_]{1,40}', data[key]):
            raise ValueError('invalid status')
    fields = {'node_01': ('do_mg_l', 'temperature_c', 'saturation_pct'),
              'node_02': ('orp_mv', 'temperature_c'),
              'node_05': ('conductivity_us_cm',)}
    if node not in fields:
        raise ValueError('unsupported node')
    for key in fields[node]:
        if key not in data:
            raise ValueError('missing measurement')
        value = data[key]
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
            raise ValueError('invalid measurement')
        if key == 'conductivity_us_cm' and value is not None and value < 0:
            raise ValueError('conductivity cannot be negative')
        if data['sensor_status'] == 'OK' and value is None:
            raise ValueError('OK requires measurements')
        if data['sensor_status'] != 'OK' and value is not None:
            raise ValueError('invalid samples must have null measurements')
    if node == 'node_05':
        if data.get('sensor_model') != 'EZO-EC':
            raise ValueError('unsupported conductivity sensor')
        setting = data.get('compensation_temperature_c')
        if setting is not None and (type(setting) not in (int, float) or not math.isfinite(setting)):
            raise ValueError('invalid compensation temperature setting')
    stamp = data.get('sample_time_utc')
    if stamp is not None:
        if not isinstance(stamp, str):
            raise ValueError('invalid sample timestamp')
        parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise ValueError('sample timestamp must be UTC')
    if data['clock_status'] == 'UNSYNCED' and stamp is not None:
        raise ValueError('unsynced sample timestamp must be null')
    if data['clock_status'] == 'SYNCED' and stamp is None:
        raise ValueError('synced timestamp missing')
    if not isinstance(data.get('raw_hex'), str) or not re.fullmatch(r'(?:[0-9a-fA-F]{2}){0,256}', data['raw_hex']):
        raise ValueError('invalid raw frame')
    if type(data.get('raw_truncated')) is not bool:
        raise ValueError('invalid raw flag')
    return data


def prediction_snapshot(path, now=None):
    now = time.time() if now is None else now
    result = {'status': 'waiting', 'server_time': now, 'horizon_hours': 12,
              'interval_hours': 1, 'latest': None}
    try:
        with Path(path).open('rb') as source:
            raw = source.read(8193)
        if len(raw) > 8192:
            raise ValueError('prediction file too large')
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError('expected prediction object')
        stamps = []
        for key in ('generated_at', 'forecast_for'):
            value = data.get(key)
            if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)', value):
                raise ValueError('prediction timestamps must be UTC')
            stamps.append(datetime.fromisoformat(value.replace('Z', '+00:00')))
        generated, target = stamps
        if generated.timestamp() > now or target - generated != timedelta(hours=12):
            raise ValueError('invalid prediction time range')
        model = data.get('model_version')
        if not isinstance(model, str) or not model.strip() or len(model) > 120:
            raise ValueError('invalid model version')
        values = data.get('values')
        allowed = {'do', 'orp', 'temperature', 'temperature_orp'}
        if not isinstance(values, dict) or not set(values) <= allowed:
            raise ValueError('invalid prediction measurements')
        for value in values.values():
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError('invalid predicted value')
        result['latest'] = {key: data[key] for key in ('generated_at', 'forecast_for', 'model_version', 'values')}
        result['status'] = 'stale' if now - generated.timestamp() > 90 * 60 else 'ready'
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        result['status'] = 'error'
    return result


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('''CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY, received_at REAL NOT NULL,
                node_id TEXT NOT NULL, boot_id TEXT NOT NULL,
                sequence INTEGER NOT NULL, payload TEXT NOT NULL,
                UNIQUE(node_id, boot_id, sequence))''')
            db.execute('CREATE INDEX IF NOT EXISTS node_time ON samples(node_id, received_at)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def ingest(self, topic, payload, now=None):
        data = validate(topic, payload)
        with self.connect() as db:
            result = db.execute('INSERT OR IGNORE INTO samples(received_at,node_id,boot_id,sequence,payload) VALUES(?,?,?,?,?)',
                                (time.time() if now is None else now, data['node_id'], data['boot_id'], data['sequence'], payload.decode('utf-8')))
            return result.rowcount == 1

    def snapshot(self, node, minutes):
        now = time.time()
        with self.connect() as db:
            latest = db.execute('SELECT received_at,payload FROM samples WHERE node_id=? ORDER BY received_at DESC,id DESC LIMIT 1', (node,)).fetchone()
            rows = db.execute('SELECT received_at,payload FROM samples WHERE node_id=? AND received_at>=? ORDER BY received_at DESC,id DESC LIMIT 1000', (node, now-minutes*60)).fetchall()
        def unpack(row):
            return {'received_at': row[0], 'sample': json.loads(row[1])}
        return {'server_time': now, 'health': health(), 'latest': unpack(latest) if latest else None,
                'history': [unpack(row) for row in reversed(rows)], 'stale_after_seconds': 20}


def handler_for(store, prediction_path=None):
    prediction_path = ROOT / 'data' / 'predictions.json' if prediction_path is None else prediction_path
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/api/predictions':
                body = json.dumps(prediction_snapshot(prediction_path), allow_nan=False).encode()
                mime = 'application/json'
            elif url.path in ('/api/node_01', '/api/node_02', '/api/node_05'):
                try:
                    minutes = int(parse_qs(url.query).get('minutes', ['15'])[0])
                    if minutes not in (15, 60):
                        raise ValueError()
                except ValueError:
                    self.send_error(400, 'Use minutes=15 or minutes=60')
                    return
                try:
                    body = json.dumps(store.snapshot(url.path.rsplit('/', 1)[1], minutes), allow_nan=False).encode()
                except (sqlite3.Error, ValueError):
                    LOG.exception('Dashboard storage read failed')
                    self.send_error(503, 'Storage unavailable')
                    return
                mime = 'application/json'
            else:
                files = {'/vt-bse-logo.png': ('gateway/images/vt-bse-logo.png', 'image/png'),
                         '/bumble-bee-logo.png': ('web/logo-company/Bumble Bee Seafood Company Logo.png', 'image/png'),
                         '/': ('web/index.html', 'text/html; charset=utf-8'), '/app.js': ('web/app.js', 'text/javascript'), '/style.css': ('web/style.css', 'text/css')}
                if url.path not in files:
                    self.send_error(404)
                    return
                file, mime = files[url.path]
                body = (ROOT / file).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass
    return Handler


def main():
    import paho.mqtt.client as mqtt
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    load_env(ROOT / 'gateway' / '.env')
    password = os.environ.get('MQTT_PASSWORD')
    if not password:
        raise SystemExit('Set MQTT_PASSWORD in gateway/.env (gateway account, not node account).')
    store = Store(ROOT / 'data' / 'telemetry.sqlite3')
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='clam-receiver', clean_session=False, manual_ack=True)
    client.username_pw_set(os.environ.get('MQTT_USER', 'clam_gateway'), password)
    client.reconnect_delay_set(1, 30)

    def connected(c, userdata, flags, reason, properties):
        health(mqtt_connected=not reason.is_failure, subscription_ready=False)
        if reason.is_failure:
            LOG.error('Broker connection rejected: %s', reason)
        else:
            c.subscribe('clam/+/telemetry', qos=1)

    def subscribed(c, userdata, mid, reasons, properties):
        ready = bool(reasons) and all(not r.is_failure for r in reasons)
        health(subscription_ready=ready)
        LOG.info('Telemetry subscription ready=%s', ready)

    def disconnected(c, userdata, flags, reason, properties):
        health(mqtt_connected=False, subscription_ready=False)
        LOG.warning('Broker disconnected: %s', reason)

    def message(c, userdata, msg):
        try:
            # Retained telemetry is not a fresh reading; firmware publishes non-retained.
            if not msg.retain:
                store.ingest(msg.topic, msg.payload)
                health(storage_error=False)
        except (ValueError, UnicodeError, TypeError, OverflowError):
            LOG.warning('Rejected invalid telemetry on %s', msg.topic)
        except sqlite3.Error:
            health(storage_error=True)
            LOG.exception('Storage failure; message not acknowledged. Repair storage then restart receiver.')
            return
        c.ack(msg.mid, msg.qos)  # Acknowledge only after the SQLite commit (or invalid-message rejection).

    client.on_connect, client.on_disconnect = connected, disconnected
    client.on_subscribe, client.on_message = subscribed, message
    server = ThreadingHTTPServer((os.environ.get('HTTP_HOST', '127.0.0.1'), int(os.environ.get('HTTP_PORT', '8000'))), handler_for(store))
    client.connect_async(os.environ.get('MQTT_HOST', '192.168.88.250'), int(os.environ.get('MQTT_PORT', '1883')), 30)
    client.loop_start()
    LOG.info('Dashboard listening on %s:%s', *server.server_address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        client.disconnect()
        client.loop_stop()


if __name__ == '__main__':
    main()
