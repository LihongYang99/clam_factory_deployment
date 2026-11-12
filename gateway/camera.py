"""Latest camera frame in memory; credentials never reach HTTP or logs."""
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
import time


class Camera:
    def __init__(self, uri):
        self.uri = uri
        self.lock = threading.Lock()
        self.frame = None
        self.received = 0
        self.monotonic = 0
        if uri:
            threading.Thread(target=self.run, daemon=True).start()

    def snapshot(self):
        with self.lock:
            fresh = self.frame is not None and time.monotonic() - self.monotonic < 10
            return (self.frame if fresh else None,
                    {'status': 'live' if fresh else 'unavailable' if self.uri else 'not_configured',
                     'received_at': self.received or None})

    def run(self):
        while True:
            process = None
            try:
                # System Python supplies Jetson's GStreamer bindings, outside the app venv.
                process = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).resolve()), '--worker'],
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                           stderr=subprocess.DEVNULL)
                process.stdin.write((self.uri + '\n').encode())
                process.stdin.close()
                buffer = bytearray()
                while True:
                    if not select.select([process.stdout], [], [], 15)[0]:
                        raise TimeoutError()
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        break
                    buffer.extend(chunk)
                    while len(buffer) >= 4:
                        size = int.from_bytes(buffer[:4], 'big')
                        if not 4 <= size <= 4_000_000:
                            raise ValueError('invalid frame size')
                        if len(buffer) < size + 4:
                            break
                        frame = bytes(buffer[4:4 + size]); del buffer[:4 + size]
                        if not (frame.startswith(b'\xff\xd8') and frame.endswith(b'\xff\xd9')):
                            raise ValueError('invalid JPEG')
                        with self.lock:
                            self.frame, self.received, self.monotonic = frame, time.time(), time.monotonic()
            except (OSError, ValueError, TimeoutError):
                pass
            finally:
                if process:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    process.stdout.close()
            time.sleep(5)


def worker():
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
    uri = sys.stdin.readline().strip()
    pipeline = Gst.parse_launch('rtspsrc name=source protocols=tcp latency=200 ! rtph264depay ! h264parse ! '
                                'avdec_h264 ! videoconvert ! videorate ! video/x-raw,framerate=1/1 ! '
                                'jpegenc quality=80 ! appsink name=sink max-buffers=1 drop=true sync=false')
    pipeline.get_by_name('source').set_property('location', uri)
    sink = pipeline.get_by_name('sink')
    pipeline.set_state(Gst.State.PLAYING)
    try:
        while True:
            sample = sink.emit('try-pull-sample', 15 * Gst.SECOND)
            if sample is None:
                break
            buf = sample.get_buffer()
            image = buf.extract_dup(0, buf.get_size())
            sys.stdout.buffer.write(len(image).to_bytes(4, 'big') + image)
            sys.stdout.buffer.flush()
    finally:
        pipeline.set_state(Gst.State.NULL)


if __name__ == '__main__':
    worker()
