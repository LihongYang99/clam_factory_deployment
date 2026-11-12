import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Store, handler_for, validate
from test_app import SAMPLE


TOPIC = 'clam/node_05/telemetry'
EC = {key: value for key, value in SAMPLE.items()
      if key not in ('do_mg_l', 'saturation_pct', 'temperature_c')}
EC.update(node_id='node_05', sensor_model='EZO-EC', conductivity_us_cm=1413.0,
          raw_hex='313431332E3030', firmware_version='0.1.0')


class Node05Tests(unittest.TestCase):
    def test_ec_schema_zero_errors_and_compensation_setting(self):
        for changes in ({}, {'conductivity_us_cm': 0},
                        {'compensation_temperature_c': 25.0},
                        {'compensation_temperature_c': None},
                        {'sensor_status': 'TIMEOUT', 'conductivity_us_cm': None, 'raw_hex': ''}):
            with self.subTest(changes=changes):
                data = dict(EC, **changes)
                self.assertEqual(validate(TOPIC, json.dumps(data).encode()), data)
                self.assertNotIn('temperature_c', data)
        invalid = [dict(EC, **changes) for changes in (
            {'conductivity_us_cm': -1}, {'conductivity_us_cm': True},
            {'conductivity_us_cm': '1413'}, {'conductivity_us_cm': float('nan')},
            {'conductivity_us_cm': float('inf')}, {'conductivity_us_cm': None},
            {'sensor_status': 'TIMEOUT'}, {'sensor_model': 'other'},
            {'compensation_temperature_c': True}, {'compensation_temperature_c': '25'},
            {'compensation_temperature_c': float('inf')},
        )]
        invalid.append({key: value for key, value in EC.items() if key != 'conductivity_us_cm'})
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate(TOPIC, json.dumps(data).encode())
        with self.assertRaises(ValueError):
            validate('clam/node_01/telemetry', json.dumps(EC).encode())

    def test_salinity_is_optional_bounded_and_persisted(self):
        for value in (None, 0, 35.2, 42):
            data = dict(EC, salinity_psu=value)
            self.assertEqual(validate(TOPIC, json.dumps(data).encode()), data)
        for value in (-1, 42.1, True, '35', float('inf')):
            with self.assertRaises(ValueError):
                validate(TOPIC, json.dumps(dict(EC, salinity_psu=value)).encode())
        with self.assertRaises(ValueError):
            validate(TOPIC, json.dumps(dict(EC, sensor_status='TIMEOUT', conductivity_us_cm=None, salinity_psu=1)).encode())
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'test.db')
            data = dict(EC, salinity_psu=35.2)
            store.ingest(TOPIC, json.dumps(data).encode())
            self.assertEqual(store.snapshot('node_05', 15)['latest']['sample']['salinity_psu'], 35.2)

    def test_nodes_store_and_api_remain_independent(self):
        orp = dict(SAMPLE, node_id='node_02', sensor_model='SEN0709', orp_mv=-120)
        orp.pop('do_mg_l')
        orp.pop('saturation_pct')
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'test.db')
            ec = dict(EC, compensation_temperature_c=25.0)
            for data in (SAMPLE, orp, ec):
                store.ingest(f'clam/{data["node_id"]}/telemetry', json.dumps(data).encode())
            self.assertFalse(store.ingest(TOPIC, json.dumps(ec).encode()))
            with store.connect() as db:
                raw = db.execute('SELECT payload FROM samples WHERE node_id=?', ('node_05',)).fetchone()[0]
                self.assertEqual(raw, json.dumps(ec))
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(store))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                for node, expected in [('node_01', SAMPLE), ('node_02', orp), ('node_05', ec)]:
                    with urlopen(f'{base}/api/{node}?minutes=60') as response:
                        snapshot = json.load(response)
                    self.assertEqual(snapshot['latest']['sample'], expected)
                    self.assertEqual([row['sample']['node_id'] for row in snapshot['history']], [node])
                error = dict(EC, sequence=34, sensor_status='TIMEOUT', conductivity_us_cm=None, raw_hex='')
                store.ingest(TOPIC, json.dumps(error).encode())
                with urlopen(base + '/api/node_05') as response:
                    snapshot = json.load(response)
                self.assertEqual(len(snapshot['history']), 2)
                self.assertIsNone(snapshot['latest']['sample']['conductivity_us_cm'])
                self.assertNotIn('temperature_c', snapshot['latest']['sample'])
                for path, status in [('/api/node_05?minutes=999', 400), ('/api/node_03', 404)]:
                    with self.assertRaises(HTTPError) as failure:
                        urlopen(base + path)
                    self.assertEqual(failure.exception.code, status)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
