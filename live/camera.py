"""Frame sources with one interface: read() -> Frame | None.

WebcamSource keeps only the latest frame (a background grabber drops stale ones) and stamps monotonic time.
VideoFileSource replays a saved clip with its container timestamps, optionally paced in real time.
"""
from dataclasses import dataclass
import threading
import time
import cv2
import numpy as np

@dataclass
class Frame:
    image: np.ndarray      # BGR, original pixels
    timestamp_ms: float    # monotonic capture time (webcam) or container PTS (file)
    frame_id: int

class WebcamSource:
    label = 'live'

    def __init__(self, device=0, width=None, height=None):
        self.cap = cv2.VideoCapture(device)
        if width: self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height: self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not self.cap.isOpened(): raise RuntimeError(f'Cannot open camera {device!r}')
        self.device = device; self._latest = None; self._next_id = 0; self.dropped = 0
        self._cond = threading.Condition(); self._stop = False; self.connected = True
        threading.Thread(target=self._grab, daemon=True).start()

    def _grab(self):
        while not self._stop:
            ok, image = self.cap.read(); now = time.monotonic() * 1000
            with self._cond:
                self.connected = ok
                if ok:
                    if self._latest is not None: self.dropped += 1  # previous frame never consumed
                    self._latest = Frame(image, now, self._next_id); self._next_id += 1
                self._cond.notify_all()
            if not ok: time.sleep(0.2)

    def read(self, timeout=1.0):
        with self._cond:
            if self._latest is None: self._cond.wait(timeout)
            frame, self._latest = self._latest, None
            return frame

    def close(self):
        self._stop = True; self.cap.release()

class VideoFileSource:
    label = 'replay'

    def __init__(self, path, realtime=False):
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened(): raise RuntimeError(f'Cannot open {path}')
        self.path = str(path); self.realtime = realtime; self._next_id = 0; self._t0 = None; self.dropped = 0; self.connected = True
        self.size = (int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))

    def read(self, timeout=None):
        ok, image = self.cap.read()
        if not ok: self.connected = False; return None
        ts = self.cap.get(cv2.CAP_PROP_POS_MSEC)
        if self.realtime:
            if self._t0 is None: self._t0 = time.monotonic() * 1000 - ts
            delay = (self._t0 + ts) / 1000 - time.monotonic()
            if delay > 0: time.sleep(delay)
        frame = Frame(image, ts, self._next_id); self._next_id += 1
        return frame

    def close(self):
        self.cap.release()

def open_source(spec, realtime=False, width=None, height=None):
    """'webcam', 'webcam:1', 'webcam:/dev/video2', or a video file path."""
    if spec.startswith('webcam'):
        device = spec.split(':', 1)[1] if ':' in spec else 0
        device = int(device) if str(device).isdigit() else device
        return WebcamSource(device, width, height)
    return VideoFileSource(spec, realtime=realtime)
