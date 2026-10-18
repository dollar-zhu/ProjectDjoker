import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
import numpy as np
from live import camera
from live.audio import Speaker
from live.pose import PoseFrame
from live.session import Session
from coaching.board_feedback import FeedbackEngine
from coaching.phraser import CanonicalPhraser

ROOT = Path(__file__).resolve().parents[1]
SERVE1 = ROOT / 'runs/dev/serve1/rtmpose_native.npz'

class FakeEstimator:
    crop_mode = 'fixed_operator'; resets = 0
    info = {'model': 'test', 'runtime': 'test', 'providers_active': ['CPU'], 'onnx_sha256': 'test'}
    def reset(self): self.resets += 1

class RecordingSpeaker(Speaker):
    def __init__(self): super().__init__('print'); self.said = []
    def speak(self, text, code=None, wait=True): self.said.append((text, code)); return super().speak(text, code, wait)

def session(tmp, allow_unvalidated_reference=False, **kw):
    engine = FeedbackEngine(ROOT / 'reference/projected2d/board_reference.json', ROOT / 'coaching/rules.json',
                            allow_unvalidated_reference=allow_unvalidated_reference)
    return Session('test', FakeEstimator(), engine, CanonicalPhraser(), RecordingSpeaker(), tmp, cooldown_s=0.0, **kw)

def pose_frames(keypoints, scores, times_ms):
    return [PoseFrame(i, t, k, s, (0, 0, 1620, 1668), (1620, 1668), 1.0) for i, (k, s, t) in enumerate(zip(keypoints, scores, times_ms))]

class SessionBehaviour(unittest.TestCase):
    def test_too_few_frames_asks_for_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = session(tmp)
            for p in pose_frames(np.zeros((5, 17, 2)), np.ones((5, 17)), [0, 30, 60, 90, 120]): s.add(p)
            s.trigger(120, wait=True)
            self.assertEqual(s.results[0]['rule_id'], 'retry_capture')
            self.assertIn('Stay in view', s.speaker.said[-1][0])
            self.assertEqual(s.state, 'READY')

    def test_duplicate_trigger_ignored_while_analyzing(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = session(tmp); s.state = 'ANALYZING'
            self.assertFalse(s.trigger(0))
            events = [json.loads(l) for l in (Path(s.dir) / 'health.jsonl').read_text().splitlines()]
            self.assertEqual(events[-1]['event'], 'trigger_ignored')

    def test_buffer_is_bounded_to_six_seconds(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = session(tmp)
            for p in pose_frames(np.zeros((400, 17, 2)), np.ones((400, 17)), np.arange(400) * 33.3): s.add(p)
            span = s.buffer[-1].timestamp_ms - s.buffer[0].timestamp_ms
            self.assertLessEqual(span, 6000); self.assertGreater(span, 5900)

    def test_disconnect_clears_buffer_and_rate_limits_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = session(tmp)
            for p in pose_frames(np.zeros((3, 17, 2)), np.ones((3, 17)), [0, 30, 60]): s.add(p)
            s.camera_fault(False); s.camera_fault(False)
            self.assertEqual(len(s.buffer), 0)
            self.assertEqual([c for _, c in s.speaker.said].count('CAMERA_DISCONNECTED'), 1)

    @unittest.skipUnless(SERVE1.exists(), 'Serve1 native output not generated')
    def test_buffered_serve_matches_offline_decision(self):
        n = np.load(SERVE1)
        with tempfile.TemporaryDirectory() as tmp:
            s = session(tmp, allow_unvalidated_reference=True)
            for p in pose_frames(n['keypoints_xy'], n['scores_raw'], n['timestamps_s'] * 1000 + 5000): s.add(p)
            s.trigger(5000 + n['timestamps_s'][-1] * 1000, wait=True)
            self.assertEqual(s.results[0]['rule_id'], 'serve_knee_loading_front_leg')
            self.assertTrue((Path(s.dir) / 'shot001' / 'dms' / 'shot001.json').exists())

class FakeCapture:
    """Stands in for cv2.VideoCapture: n frames at ~200 fps, then the device disappears."""
    def __init__(self, *a): self.i = 0
    def isOpened(self): return True
    def set(self, *a): return True
    def read(self):
        time.sleep(0.005); self.i += 1
        return (self.i <= 40, np.zeros((4, 4, 3), np.uint8) if self.i <= 40 else None)
    def release(self): pass

class Webcam(unittest.TestCase):
    def test_latest_frame_only_and_disconnect_flag(self):
        with mock.patch.object(camera.cv2, 'VideoCapture', FakeCapture):
            cam = camera.WebcamSource(0)
            time.sleep(0.1); first = cam.read()
            time.sleep(0.5)
            self.assertIsNotNone(first); self.assertGreater(cam.dropped, 0)  # slow consumer -> stale frames dropped
            self.assertFalse(cam.connected); cam.close()

VOICE = ROOT / 'models/piper/en_US-joe-medium.onnx'

class Speech(unittest.TestCase):
    def test_piper_without_voice_falls_back_to_text(self):
        with mock.patch('live.audio.shutil.which', return_value=None):
            spk = Speaker('piper', voice='/nonexistent/voice.onnx')
            r = spk.speak('Good leg drive.', 'GOOD_LEG_DRIVE')
        self.assertIsNotNone(spk.voice_error); self.assertTrue(r.ok); self.assertEqual(r.backend, 'print')

    @unittest.skipUnless(VOICE.exists(), 'Piper voice not downloaded')
    def test_piper_synthesizes_and_plays_through_player(self):
        import wave
        spk = Speaker('piper', voice=str(VOICE)); self.assertIsNone(spk.voice_error)
        import shutil; true = shutil.which('true')  # stand-in player: no sound during tests
        with mock.patch('live.audio.shutil.which', side_effect=lambda t: true if t == 'aplay' else None):
            r = spk.speak('Bend both knees a little more as the ball goes up.')
        self.assertEqual((r.ok, r.backend), (True, 'piper'))
        with wave.open(str(spk._tmp_wav)) as w: self.assertGreater(w.getnframes() / w.getframerate(), 1.0)

if __name__ == '__main__':
    unittest.main()
