"""estimate(Frame) -> PoseFrame with a pluggable 2D pose backend (no person detector).

Backend contract (e.g. our ONNX RTMPose runner, or the team's QCRTMPose package via a thin adapter):
    backend.estimate(image_bgr, box_xyxy) -> (keypoints (17,2) original pixels in COCO-17 order, scores (17,))
    backend.info -> dict with at least runtime, providers_active, onnx_sha256 (or artifact hash)
Crop modes: a fixed operator crop, or pose-tracked (previous confident keypoints define the next crop).
"""
from dataclasses import dataclass
import time
import numpy as np

@dataclass
class PoseFrame:
    frame_id: int
    timestamp_ms: float
    keypoints: np.ndarray   # (17,2) original pixels, COCO-17 = canonical17
    scores: np.ndarray      # (17,) backend scores
    crop_xyxy: tuple
    image_size: tuple       # (width, height)
    inference_ms: float

def make_pose_backend(cfg):
    """cfg: {'backend': 'rtmpose-onnx', 'model_dir' | ('model', 'cache'), 'provider'}."""
    cfg = cfg or {}; kind = cfg.get('backend', 'rtmpose-onnx')
    if kind == 'rtmpose-onnx':
        from pose2d.rtmpose import RTMPose, fetch_model
        model_dir = cfg.get('model_dir') or fetch_model(cfg.get('model', 'rtmpose-m-body7-256x192'), cfg.get('cache', 'models'))
        return RTMPose(model_dir, providers=cfg.get('providers') or [cfg.get('provider', 'CPUExecutionProvider')])
    raise ValueError(f"Unknown pose backend {kind!r}; add an adapter implementing estimate(image, box) and info")

class PoseEstimator:
    TRACK_MIN_JOINTS, TRACK_MIN_SCORE, TRACK_MARGIN = 8, 0.3, 0.15

    def __init__(self, backend, crop=None):
        self.backend = backend
        self.fixed = tuple(float(v) for v in crop) if crop else None; self._track = None
        self.crop_mode = 'fixed_operator' if crop else 'pose_tracked'

    @property
    def info(self):
        return self.backend.info

    def estimate(self, frame):
        h, w = frame.image.shape[:2]; box = self.fixed or self._track or (0, 0, w, h); t0 = time.perf_counter()
        kp, sc = self.backend.estimate(frame.image, box); ms = (time.perf_counter() - t0) * 1000
        if not self.fixed:
            good = sc >= self.TRACK_MIN_SCORE
            if good.sum() >= self.TRACK_MIN_JOINTS:
                (x1, y1), (x2, y2) = kp[good].min(0), kp[good].max(0); m = self.TRACK_MARGIN * max(x2 - x1, y2 - y1)
                self._track = (max(0, x1 - m), max(0, y1 - m), min(w, x2 + m), min(h, y2 + m))
            else:
                self._track = None
        return PoseFrame(frame.frame_id, frame.timestamp_ms, kp, sc, tuple(float(v) for v in box), (w, h), ms)

    def reset(self):
        self._track = None
