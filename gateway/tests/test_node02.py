import json
import tempfile
import unittest
from pathlib import Path
from app import Store, validate
from test_app import SAMPLE

class Node02Test(unittest.TestCase):
    def test_separate_nodes_and_orp_schema(self):
        orp = dict(SAMPLE, node_id='node_02', sensor_model='SEN0709', orp_mv=-120, temperature_c=23.4)
        orp.pop('do_mg_l'); orp.pop('saturation_pct')
        payload = json.dumps(orp).encode()
        self.assertEqual(validate('clam/node_02/telemetry', payload)['orp_mv'], -120)
        with self.assertRaises(ValueError):
            validate('clam/node_01/telemetry', payload)
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'test.db')
            store.ingest('clam/node_02/telemetry',payload)
            self.assertIsNone(store.snapshot('node_01',15)['latest'])
            self.assertEqual(store.snapshot('node_02',15)['latest']['sample']['temperature_c'],23.4)
