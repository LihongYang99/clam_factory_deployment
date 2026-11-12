import sys
from pathlib import Path
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camera import Camera

class CameraTests(unittest.TestCase):
    def test_freshness_and_private_status(self):
        c = Camera('')
        self.assertEqual(c.snapshot()[1]['status'], 'not_configured')
        c.uri = 'rtsp://private-credential'
        c.frame = b'jpeg'; c.received = time.time(); c.monotonic = time.monotonic()
        frame, status = c.snapshot()
        self.assertEqual(frame, b'jpeg')
        self.assertEqual(status['status'], 'live')
        self.assertNotIn('private', str(status))
        c.monotonic -= 11
        self.assertIsNone(c.snapshot()[0])
        self.assertEqual(c.snapshot()[1]['status'], 'unavailable')
