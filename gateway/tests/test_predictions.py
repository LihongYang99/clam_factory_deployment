import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Store, handler_for, prediction_snapshot


NOW = datetime(2026, 11, 11, 17, tzinfo=timezone.utc).timestamp()


def batch(generated=NOW):
    stamp = datetime.fromtimestamp(generated, timezone.utc)
    return {'generated_at': stamp.isoformat(),
            'forecast_for': (stamp + timedelta(hours=12)).isoformat(),
            'model_version': 'test-model',
            'values': {'do': 6.2, 'orp': 190.0, 'temperature': None}}


class PredictionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'predictions.json'

    def write(self, data):
        self.path.write_text(json.dumps(data))

    def test_missing_ready_and_stale(self):
        self.assertEqual(prediction_snapshot(self.path, NOW)['status'], 'waiting')
        for age, status in ((0, 'ready'), (5400, 'ready'), (5401, 'stale')):
            with self.subTest(age=age):
                data = batch(NOW - age)
                self.write(data)
                result = prediction_snapshot(self.path, NOW)
                self.assertEqual(result['status'], status)
                self.assertEqual(result['latest'], data)
                self.assertEqual(result['horizon_hours'], 12)
                self.assertEqual(result['interval_hours'], 1)
                self.assertIsNone(result['latest']['values']['temperature'])
                self.assertNotIn('temperature_orp', result['latest']['values'])

    def test_invalid_results_never_become_forecasts(self):
        invalid = [None, [], batch(NOW + 1)]
        for changes in ({'generated_at': '2026-11-11'},
                        {'generated_at': '2026-11-11T17:00:00'},
                        {'generated_at': '2026-11-11T17:00:00-05:00'},
                        {'forecast_for': '2026-11-12T06:00:00Z'},
                        {'model_version': ' '}, {'model_version': 'x' * 121},
                        {'values': []}, {'values': {'unknown': 1}},
                        {'values': {'do': True}}, {'values': {'do': '6.2'}},
                        {'values': {'orp': float('inf')}},
                        {'values': {'temperature': float('nan')}}):
            invalid.append(dict(batch(), **changes))
        for data in invalid:
            with self.subTest(data=data):
                self.write(data)
                result = prediction_snapshot(self.path, NOW)
                self.assertEqual(result['status'], 'error')
                self.assertIsNone(result['latest'])
        for raw in (b'{"partial":', b'x' * 8193, b'\xff', b'[' * 2000 + b']' * 2000):
            self.path.write_bytes(raw)
            self.assertEqual(prediction_snapshot(self.path, NOW)['status'], 'error')
        with patch.object(Path, 'open', side_effect=PermissionError):
            self.assertEqual(prediction_snapshot(self.path, NOW)['status'], 'error')

    def test_http_endpoint_and_file_stays_private(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0),
                                    handler_for(Store(Path(self.folder.name) / 'samples.db'), self.path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base + '/api/predictions') as response:
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
                self.assertEqual(json.load(response)['status'], 'waiting')
            self.write(batch())
            with patch('app.time.time', return_value=NOW), urlopen(base + '/api/predictions') as response:
                self.assertEqual(json.load(response)['latest']['values']['do'], 6.2)
            with self.assertRaises(HTTPError) as error:
                urlopen(base + '/data/predictions.json')
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
