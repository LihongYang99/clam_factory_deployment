import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import ROOT, Store, handler_for, validate

SAMPLE = dict(schema_version=1, node_id='node_01', boot_id='3b65b0a7f176469f', sequence=33,
              uptime_ms=161002, not_forwarded_before_sample=27, sensor_status='OK',
              clock_status='UNSYNCED', calibration_status='UNVERIFIED', compensation_status='UNVERIFIED',
              sample_time_utc=None, do_mg_l=6.1542, temperature_c=25.3423, saturation_pct=89.165,
              raw_hex='01030C3F64433240C4EF3C41CABD1E9193', raw_truncated=False, firmware_version='0.1.3')
TOPIC='clam/node_01/telemetry'

class Tests(unittest.TestCase):
    def test_reject_bad_boundaries(self):
        for changes in ({'sequence': True}, {'do_mg_l': float('nan')}, {'do_mg_l': '6'},
                        {'sensor_status':'TIMEOUT'}, {'boot_id':'../'}, {'schema_version':True},
                        {'sample_time_utc':'2026-11-06T00:00:00Z'}, {'raw_hex':'XYZ'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate(TOPIC,json.dumps(dict(SAMPLE,**changes)).encode())
        with self.assertRaises(ValueError):validate('clam/node_02/telemetry',json.dumps(SAMPLE).encode())
        with self.assertRaises(ValueError):validate(TOPIC,b'x'*8193)

    def test_commit_deduplicate_and_preserve_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'samples.db')
            raw=json.dumps(SAMPLE).encode()
            self.assertTrue(store.ingest(TOPIC,raw))
            self.assertFalse(store.ingest(TOPIC,raw))
            failure=dict(SAMPLE,sequence=34,sensor_status='TIMEOUT',do_mg_l=None,temperature_c=None,saturation_pct=None,raw_hex='')
            store.ingest(TOPIC,json.dumps(failure).encode())
            snapshot=Store(Path(folder)/'samples.db').snapshot('node_01',15)
            self.assertEqual(len(snapshot['history']),2)
            self.assertIsNone(snapshot['latest']['sample']['do_mg_l'])
            self.assertIsNone(snapshot['latest']['sample']['sample_time_utc'])
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT payload FROM samples ORDER BY id LIMIT 1').fetchone()[0],raw.decode())

    def test_api_and_static_allowlist(self):
        with tempfile.TemporaryDirectory() as folder:
            server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(Store(Path(folder)/'samples.db')))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base+'/api/node_01') as response:
                    self.assertIsNone(json.load(response)['latest'])
                for path in ('/','/app.js','/style.css','/vt-bse-logo.png','/bumble-bee-logo.png'):
                    with urlopen(base+path) as response:self.assertEqual(response.status,200)
                with urlopen(base+'/bumble-bee-logo.png') as response:
                    self.assertEqual(response.headers['Content-Type'], 'image/png')
                    image = response.read()
                    self.assertEqual(image[:8], b'\x89PNG\r\n\x1a\n')
                    self.assertEqual(image, (ROOT/'web/logo-company/Bumble Bee Seafood Company Logo.png').read_bytes())
                for path,code in [('/api/node_01?minutes=999',400),('/gateway/.env',404),('/../README.md',404),('/web/logo-company/Bumble%20Bee%20Seafood%20Company%20Logo.png',404)]:
                    with self.assertRaises(HTTPError) as error:urlopen(base+path)
                    self.assertEqual(error.exception.code,code)
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
