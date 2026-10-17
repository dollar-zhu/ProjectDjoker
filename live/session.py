"""READY -> ANALYZING -> FEEDBACK -> COOLDOWN -> READY around a 6 s pose buffer.

Composition: Session(source_label, estimator, engine, phraser, speaker, out_dir). Each part is replaceable:
estimator.estimate(Frame) -> PoseFrame, engine(packet_path) -> Feedback, phraser.phrase(Feedback) -> speech dict,
speaker.speak(text, code) -> AudioResult. Capture keeps running while a shot is analyzed (worker thread).
"""
from collections import deque
import json
import threading
import time
from pathlib import Path
import numpy as np
from dms.contract import export_canonical
from pose2d.rtmpose import COCO17_EVIDENCE

BUFFER_S = 6.0
RETRY = {'mode': 'retry', 'rule_id': 'retry_capture', 'suggestion': None, 'speech_codes': ['RETRY_CAPTURE'],
         'canonical_text': "I couldn't see that serve clearly. Stay in view and try again."}

class Session:
    def __init__(self, source_label, estimator, engine, phraser, speaker, out_dir, *, window_s=4.0, min_frames=15,
                 handedness='right', camera_view='behind_server', player='player', cooldown_s=2.0):
        self.estimator, self.engine, self.phraser, self.speaker = estimator, engine, phraser, speaker
        self.label = source_label
        self.session_id = time.strftime('%Y%m%d-%H%M%S') + f'-{source_label}'
        self.dir = Path(out_dir) / self.session_id; self.dir.mkdir(parents=True, exist_ok=True)
        self.window_ms, self.min_frames, self.cooldown_s = window_s * 1000, min_frames, cooldown_s
        self.meta = dict(handedness=handedness, camera_view=camera_view, player=player)
        self.buffer = deque(); self.state = 'READY'; self.shots = 0; self.results = []
        self._lock = threading.Lock(); self._last_fault = 0.0

    # ---- logging -------------------------------------------------------------------------------------------
    def log(self, name, record):
        with open(self.dir / f'{name}.jsonl', 'a') as f: f.write(json.dumps(record) + '\n')

    def set_state(self, state):
        self.state = state; self.log('health', {'t': time.time(), 'state': state})

    # ---- capture -------------------------------------------------------------------------------------------
    def add(self, pose_frame):
        with self._lock:
            self.buffer.append(pose_frame)
            while self.buffer and pose_frame.timestamp_ms - self.buffer[0].timestamp_ms > BUFFER_S * 1000: self.buffer.popleft()

    def camera_fault(self, connected):
        if connected: return
        with self._lock: self.buffer.clear()
        self.estimator.reset(); now = time.monotonic()
        if now - self._last_fault > 10:  # rate-limit repeated fault messages
            self._last_fault = now; self.log('health', {'t': time.time(), 'event': 'camera_disconnected'})
            self.speaker.speak('Camera disconnected.', 'CAMERA_DISCONNECTED')

    def trigger(self, trigger_ms, wait=False):
        """Completion trigger: analyze the preceding window. Triggers outside READY are ignored (no duplicates)."""
        if self.state != 'READY':
            self.log('health', {'t': time.time(), 'event': 'trigger_ignored', 'state': self.state}); return False
        with self._lock:
            window = [p for p in self.buffer if trigger_ms - self.window_ms <= p.timestamp_ms <= trigger_ms]
        self.shots += 1; shot = f'shot{self.shots:03d}'; self.set_state('ANALYZING')
        worker = threading.Thread(target=self._analyze, args=(shot, window), daemon=True); worker.start()
        if wait: worker.join()
        return True

    # ---- analysis ------------------------------------------------------------------------------------------
    def _analyze(self, shot, window):
        t0 = time.perf_counter(); timings = {'shot': shot, 'frames': len(window), 'source': self.label}
        shot_dir = self.dir / shot
        try:
            if len(window) < self.min_frames:
                fb = dict(RETRY, shot_id=shot, reason='too_few_frames')
            else:
                fb = self.engine(self.export(shot_dir, shot, window))
            timings['analysis_ms'] = (time.perf_counter() - t0) * 1000
            speech = self.phraser.phrase(fb); timings['phrase_ms'] = speech.get('latency_ms')
            shot_dir.mkdir(parents=True, exist_ok=True)
            (shot_dir / 'feedback.json').write_text(json.dumps(fb, indent=2) + '\n')
            (shot_dir / 'speech.json').write_text(json.dumps(speech, indent=2) + '\n')
            self.set_state('FEEDBACK'); timings['trigger_to_audio_ms'] = (time.perf_counter() - t0) * 1000
            result = self.speaker.speak(speech['speech'], (fb.get('speech_codes') or [None])[-1])
            timings.update(audio_backend=result.backend, audio_ok=result.ok, speech_source=speech['source'])
            score = (fb.get('rating') or {}).get('score'); timings['score'] = score
            self.results.append({'shot': shot, 'rule_id': fb.get('rule_id'), 'mode': fb.get('mode'), 'score': score, 'speech': speech['speech']})
        except Exception as exc:  # noqa: BLE001 - one bad shot must not end the session
            timings['error'] = repr(exc); self.speaker.speak('Something went wrong. Please serve again.', 'RETRY_CAPTURE')
        finally:
            self.log('timings', timings)
            self.set_state('COOLDOWN'); time.sleep(self.cooldown_s); self.set_state('READY')

    def export(self, shot_dir, shot, window):
        """PoseFrames -> DMS v0.1 packet (missing joints NaN, observed timestamps rebased to zero)."""
        kp = np.array([p.keypoints for p in window], float); raw = np.array([p.scores for p in window], float)
        w, h = window[0].image_size; t = np.array([p.timestamp_ms for p in window]) / 1000
        keep = np.concatenate([[True], np.diff(t) > 0]); kp, raw, t = kp[keep], raw[keep], t[keep]
        outside = (kp[..., 0] < 0) | (kp[..., 0] > w - 1) | (kp[..., 1] < 0) | (kp[..., 1] > h - 1)
        missing = (raw <= 0) | outside; pose = kp.copy(); pose[missing] = np.nan
        conf = np.clip(raw, 0, 1); conf[missing] = np.nan
        shot_dir.mkdir(parents=True, exist_ok=True)
        np.savez(shot_dir / 'rtmpose_native.npz', keypoints_xy=kp, scores_raw=raw, timestamps_s=t,
                 frame_id=np.array([p.frame_id for p in window])[keep], crop_xyxy=np.array([p.crop_xyxy for p in window])[keep])
        info = self.estimator.info
        source = {'model': info.get('model', 'rtmpose-m-body7-256x192'), 'coordinate_system': 'image_2d',
                  'camera_view': self.meta['camera_view'], 'fps': None, 'axis_convention': 'x_right_y_down', 'units': 'pixels',
                  'metric_space': True, 'image_size': [w, h], 'comparison_profile_id': None, 'runtime': info.get('runtime'),
                  'runtime_provider': (info.get('providers_active') or [None])[0], 'onnx_sha256': info.get('onnx_sha256'),
                  'crop_mode': self.estimator.crop_mode, 'capture': self.label}
        return export_canonical(shot_dir / 'dms', shot_id=shot, player=self.meta['player'], handedness=self.meta['handedness'],
                                source=source, pose=pose, timestamps=t - t[0], joint_confidence=conf, confidence_kind='tracking_score',
                                score_definition='rtmpose-simcc-mean-xy-peak-raw-clipped-0-1', mapping_evidence=COCO17_EVIDENCE,
                                events={'max_knee_flexion': None, 'contact': None})
