"""djoker-check: prove a device can run the serve coach, and save the evidence as JSON.

Checks platform, packages and execution providers, asset hashes, golden pose inference against the development
host (pixel error + latency), golden feedback decisions, and optionally camera, audio and the Qwen endpoint.
"""
import argparse
import json
import platform
import shutil
import sys
import time
import os
from pathlib import Path
import numpy as np

PASS, WARN, FAIL = 'PASS', 'WARN', 'FAIL'

GOLDEN_ENV = 'DJOKER_GOLDEN'

class GoldenMissing(Exception):
    pass

def golden_dir(cfg):
    """Golden fixtures are private (they contain a real player) and live outside the package:
    config check.golden_dir, else $DJOKER_GOLDEN. Create them with scripts/make_golden.py."""
    for cand in ((cfg.get('check') or {}).get('golden_dir'), os.environ.get(GOLDEN_ENV)):
        if cand and (Path(cand) / 'expected_pose.json').exists(): return Path(cand)
    return None

def golden(cfg, name):
    d = golden_dir(cfg)
    if d is None: raise GoldenMissing(f'golden fixtures not found (set check.golden_dir or ${GOLDEN_ENV}); skipped')
    return d / name

def check_platform():
    import cv2, onnxruntime as ort
    providers = ort.get_available_providers()
    detail = {'python': sys.version.split()[0], 'machine': platform.machine(), 'system': platform.platform(),
              'libc': ' '.join(platform.libc_ver()), 'numpy': np.__version__, 'opencv': cv2.__version__,
              'onnxruntime': ort.__version__, 'providers_available': providers}
    status = PASS if sys.version_info >= (3, 10) else FAIL
    note = 'QNNExecutionProvider available (NPU path possible, not yet used)' if 'QNNExecutionProvider' in providers else 'CPU execution'
    return status, note, detail

def check_assets(cfg):
    from pose2d.rtmpose import fetch_model, MODELS
    pose = cfg['pose']; detail = {}
    try:
        model_dir = fetch_model(pose.get('model', 'rtmpose-m-body7-256x192'), pose.get('cache', 'models'))
        detail['model_dir'] = str(model_dir); detail['onnx_sha256'] = MODELS[pose.get('model', 'rtmpose-m-body7-256x192')]['onnx_sha256']
    except Exception as exc:  # noqa: BLE001
        return FAIL, f'model missing or hash mismatch: {exc}', detail
    for key in ('table', 'rules'):
        path = Path(cfg['reference'][key])
        if not path.exists(): return FAIL, f'{key} missing: {path}', detail
        data = json.loads(path.read_text()); detail[key] = {'path': str(path), 'version': data.get('version')}
    return PASS, 'model hash verified; reference table and rules present', detail

def check_golden_pose(cfg, runs=20):
    import cv2
    from live.pose import make_pose_backend
    expected = json.loads(golden(cfg, 'expected_pose.json').read_text())
    backend = make_pose_backend(cfg['pose']); image = cv2.imread(str(golden(cfg, expected['image'])))
    kp, sc = backend.estimate(image, expected['box_xyxy'])
    err = np.linalg.norm(kp - np.array(expected['keypoints_xy']), axis=1)
    times = []
    for _ in range(runs):
        t0 = time.perf_counter(); backend.estimate(image, expected['box_xyxy']); times.append((time.perf_counter() - t0) * 1000)
    detail = {'max_px_error': float(err.max()), 'median_px_error': float(np.median(err)), 'tolerance_px': expected['tolerance_px'],
              'max_score_diff': float(np.abs(sc - np.array(expected['scores'])).max()),
              'latency_ms_median': float(np.median(times)), 'latency_ms_p95': float(np.percentile(times, 95)),
              'pose_only_fps_estimate': float(1000 / np.median(times)), 'provider_active': backend.info['providers_active'][0]}
    if err.max() > expected['tolerance_px']: return FAIL, f"skeleton differs from dev host by {err.max():.1f}px", detail
    status = PASS if detail['pose_only_fps_estimate'] >= 10 else WARN
    return status, f"max error {err.max():.1f}px; {detail['latency_ms_median']:.1f} ms/frame (~{detail['pose_only_fps_estimate']:.0f} fps pose only)", detail

def check_golden_decisions(cfg):
    from coaching.board_feedback import FeedbackEngine
    spec = json.loads(golden(cfg, 'expected_decisions.json').read_text()); packet = golden(cfg, spec['packet']); detail = {}
    for mode, allow in (('strict', False), ('demo', True)):
        engine = FeedbackEngine(cfg['reference']['table'], cfg['reference']['rules'], spec['serve_type'], allow)
        t0 = time.perf_counter(); fb = engine(packet); ms = (time.perf_counter() - t0) * 1000
        got = {k: (fb.get('rating') or {}).get('score') if k == 'score' else fb.get(k) for k in spec['expected'][mode]}
        detail[mode] = {'expected': spec['expected'][mode], 'got': got, 'ms': ms, 'canonical_text': fb['canonical_text']}
        if got != spec['expected'][mode]: return FAIL, f'{mode} decision differs: {got}', detail
    return PASS, 'strict and demo decisions match the dev host', detail

def check_camera(spec, seconds=3.0):
    from live.camera import open_source
    detail = {'devices': sorted(str(p) for p in Path('/dev').glob('video*')) if Path('/dev').exists() else []}
    if not spec: return WARN, 'camera not opened (pass --camera webcam:/dev/videoN)', detail
    try:
        src = open_source(spec); frames = 0; t0 = time.perf_counter(); shape = None
        while time.perf_counter() - t0 < seconds:
            f = src.read()
            if f is not None: frames += 1; shape = f.image.shape
        src.close()
    except Exception as exc:  # noqa: BLE001
        return FAIL, f'cannot read {spec}: {exc}', detail
    detail.update(frames=frames, capture_fps=frames / seconds, frame_shape=shape)
    return (PASS if frames / seconds >= 10 else WARN), f'{frames / seconds:.1f} fps at {shape}', detail

def check_audio(backend, speak, wav_dir=None, voice=None):
    from live.audio import Speaker
    tools = {t: bool(shutil.which(t)) for t in ('espeak-ng', 'aplay', 'afplay', 'say')}
    need = {'say': ['say'], 'espeak': ['espeak-ng'], 'wav': ['aplay', 'afplay'], 'piper': ['aplay', 'afplay'], 'print': []}[backend]
    detail = {'tools': tools, 'configured_backend': backend}
    if backend == 'print': return WARN, 'audio backend is print (text only)', detail
    if not any(tools[t] for t in need): return FAIL, f"backend {backend} needs {' or '.join(need)}, not found", detail
    if backend == 'piper':
        t0 = time.perf_counter(); spk = Speaker('piper', wav_dir or 'audio', voice); detail.update(voice=voice, load_ms=(time.perf_counter() - t0) * 1000)
        if spk.voice_error: return FAIL, f'piper voice did not load ({spk.voice_error})', detail
        t0 = time.perf_counter(); wav = spk._piper_wav('Djoker check. Audio is working.'); detail['synth_ms'] = (time.perf_counter() - t0) * 1000
        if wav is None: return FAIL, 'piper synthesis failed', detail
        if speak:
            r = spk.speak('Djoker check. Audio is working.', 'READY'); detail['spoke'] = r.ok
            if not r.ok or r.backend != 'piper': return FAIL, f'speech did not play ({r.error or r.backend})', detail
        return (PASS if detail['synth_ms'] <= 1000 else WARN), f"piper {Path(voice).stem}: {detail['synth_ms']:.0f} ms to synthesize a test sentence", detail
    if backend == 'wav':
        codes = json.loads((Path(wav_dir) / 'speech_codes.json').read_text()) if wav_dir and (Path(wav_dir) / 'speech_codes.json').exists() else {}
        missing = [c for c in codes if not (Path(wav_dir) / f'{c}.wav').exists()]
        detail['missing_wavs'] = missing
        if missing: return WARN, f'{len(missing)} prerecorded WAVs missing; those cues fall back to TTS or text', detail
    if speak:
        r = Speaker(backend, wav_dir or 'audio').speak('Djoker check. Audio is working.', 'READY'); detail['spoke'] = r.ok
        if not r.ok or r.backend == 'print': return FAIL, f'speech did not play ({r.error or r.backend})', detail
    return PASS, f"backend {backend} via {', '.join(t for t in need if tools[t])}", detail

def check_qwen(cfg):
    from coaching.phraser import QwenPhraser
    ph = cfg.get('phraser', {})
    if ph.get('backend') != 'qwen': return WARN, 'Qwen disabled in config (canonical speech only)', {}
    spec = json.loads(golden(cfg, 'expected_decisions.json').read_text())
    from coaching.board_feedback import FeedbackEngine
    fb = FeedbackEngine(cfg['reference']['table'], cfg['reference']['rules'], 'unknown', True)(golden(cfg, spec['packet']))
    r = QwenPhraser(ph['url'], ph.get('model', 'qwen'), float(ph.get('timeout_s', 1.0))).phrase(fb)
    detail = {'url': ph['url'], 'model': ph.get('model'), **r}
    if r['source'] != 'qwen': return WARN, f"fell back to canonical text ({', '.join(r.get('reasons', []))})", detail
    return (PASS if r['latency_ms'] <= 1000 else WARN), f"{r['latency_ms']:.0f} ms: \"{r['speech']}\"", detail

def main(argv=None):
    from live.pipeline import load_config
    from live.runner import DEFAULT_CONFIG
    p = argparse.ArgumentParser(prog='djoker-check', description=__doc__)
    p.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    p.add_argument('--camera', help="Open this source for a few seconds, e.g. webcam:/dev/video0")
    p.add_argument('--speak', action='store_true', help='Actually play a test sentence')
    p.add_argument('--report', type=Path, help='Where to write the JSON report (default: runs/board_check_<time>.json)')
    a = p.parse_args(argv)
    cfg = load_config(a.config)
    checks = [('platform', lambda: check_platform()), ('assets', lambda: check_assets(cfg)),
              ('golden_pose', lambda: check_golden_pose(cfg)), ('golden_decisions', lambda: check_golden_decisions(cfg)),
              ('camera', lambda: check_camera(a.camera)), ('audio', lambda: check_audio(cfg['audio']['backend'], a.speak, cfg['audio'].get('wav_dir'), cfg['audio'].get('voice'))),
              ('qwen', lambda: check_qwen(cfg))]
    report = {'tool': 'djoker-check', 'time': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'config': cfg['_config_path'], 'checks': {}}
    for name, fn in checks:
        try: status, note, detail = fn()
        except GoldenMissing as exc: status, note, detail = WARN, str(exc), {}
        except Exception as exc:  # noqa: BLE001 - report, keep checking
            status, note, detail = FAIL, f'{type(exc).__name__}: {exc}', {}
        report['checks'][name] = {'status': status, 'note': note, 'detail': detail}
        print(f'{status:4s}  {name:16s} {note}', flush=True)
    out = a.report or Path(cfg['session']['out_dir']) / f"board_check_{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(report, indent=2, default=str) + '\n')
    print(f'report: {out}')
    return 1 if any(c['status'] == FAIL for c in report['checks'].values()) else 0

if __name__ == '__main__':
    sys.exit(main())
