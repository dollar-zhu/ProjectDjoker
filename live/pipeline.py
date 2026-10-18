"""Build the serve-coach pipeline from one JSON config. Relative paths resolve against the config file's folder.

    {"source":   {"spec": "webcam:/dev/video0" | "<video path>", "width": 1280, "height": 720, "realtime": false},
     "pose":     {"backend": "rtmpose-onnx", "model": "rtmpose-m-body7-256x192", "cache": "<models dir>",
                  "provider": "CPUExecutionProvider", "crop": null | [x1, y1, x2, y2]},
     "analysis": {"window_s": 4.0, "min_frames": 15, "handedness": "right", "camera_view": "behind_server", "serve_type": "unknown"},
     "reference":{"table": "<board_reference.json>", "rules": "<rules.json>", "rating": "<rating.json>",
                  "allow_unvalidated_reference": false},
     "phraser":  {"backend": "canonical" | "qwen", "url": "...", "model": "...", "timeout_s": 1.0},
     "audio":    {"backend": "print" | "piper" | "say" | "espeak" | "wav", "wav_dir": "<audio dir>", "voice": "<piper .onnx>"},
     "session":  {"cooldown_s": 2.0, "out_dir": "runs"}}
"""
import copy
import json
from dataclasses import dataclass
from pathlib import Path
from .camera import open_source
from .pose import PoseEstimator, make_pose_backend
from .audio import Speaker
from .session import Session
from coaching.board_feedback import FeedbackEngine
from coaching.phraser import make_phraser

PATH_KEYS = {('pose', 'cache'), ('pose', 'model_dir'), ('reference', 'table'), ('reference', 'rules'), ('reference', 'rating'),
             ('audio', 'wav_dir'), ('audio', 'voice'), ('session', 'out_dir'), ('check', 'golden_dir')}

def load_config(path, overrides=None):
    path = Path(path).resolve(); cfg = json.loads(path.read_text())
    for section, values in (overrides or {}).items():
        cfg.setdefault(section, {}).update({k: v for k, v in values.items() if v is not None})
    for section, key in PATH_KEYS:  # resolve relative to the config file, not the working directory
        value = cfg.get(section, {}).get(key)
        if value and not Path(value).is_absolute(): cfg[section][key] = str((path.parent / value).resolve())
    spec = cfg.get('source', {}).get('spec')
    if spec and not spec.startswith('webcam') and not Path(spec).is_absolute() and not Path(spec).exists():
        candidate = path.parent / spec
        if candidate.exists(): cfg['source']['spec'] = str(candidate.resolve())
    cfg['_config_path'] = str(path)
    return cfg

@dataclass
class Pipeline:
    config: dict
    source: object
    estimator: PoseEstimator
    engine: FeedbackEngine
    phraser: object
    speaker: Speaker
    session: Session

def build(cfg):
    cfg = copy.deepcopy(cfg); src = cfg['source']; pose = cfg.get('pose', {}); ana = cfg.get('analysis', {})
    ref = cfg['reference']; ses = cfg.get('session', {}); is_file = not src['spec'].startswith('webcam')
    source = open_source(src['spec'], realtime=src.get('realtime', False), width=src.get('width'), height=src.get('height'))
    estimator = PoseEstimator(make_pose_backend(pose), crop=pose.get('crop'))
    engine = FeedbackEngine(ref['table'], ref['rules'], ana.get('serve_type', 'unknown'), ref.get('allow_unvalidated_reference', False),
                            rating=ref.get('rating'))
    phraser = make_phraser(cfg.get('phraser'))
    aud = cfg.get('audio', {})
    from .bluetooth import BluetoothRoute
    route = BluetoothRoute(aud['bluetooth_address']) if aud.get('bluetooth_address') else None
    speaker = Speaker(aud.get('backend', 'print'), aud.get('wav_dir', 'audio'), aud.get('voice'), route=route)
    cooldown = 0.0 if is_file and not src.get('realtime') else ses.get('cooldown_s', 2.0)
    session = Session(source.label, estimator, engine, phraser, speaker, ses.get('out_dir', 'runs'),
                      window_s=ana.get('window_s', 4.0), min_frames=ana.get('min_frames', 15),
                      handedness=ana.get('handedness', 'right'), camera_view=ana.get('camera_view', 'behind_server'),
                      cooldown_s=cooldown)
    (session.dir / 'config.json').write_text(json.dumps(cfg, indent=2) + '\n')
    return Pipeline(cfg, source, estimator, engine, phraser, speaker, session)
