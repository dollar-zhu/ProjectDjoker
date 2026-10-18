"""djoker-run: serve coach on a webcam or a saved video, configured by a JSON file.

Webcam: press Enter right after each serve (stand-in for the physical completion button); 'q' + Enter quits.
Video:  one serve per clip - analyzes the last window_s seconds once at the end (or at --trigger-at times).
"""
import argparse
import sys
import threading
import time
from pathlib import Path
from .pipeline import load_config, build

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / 'config' / 'dev.json'

def run(pipe, trigger_at=None, stop=None, keyboard=True):
    source, session, speaker, estimator = pipe.source, pipe.session, pipe.speaker, pipe.estimator
    is_file = source.label == 'replay'; stop = stop or threading.Event()
    print(f'session {session.session_id} -> {session.dir}  (pose crop: {estimator.crop_mode}; '
          f'phraser: {pipe.phraser.name}; audio: {speaker.backend})', flush=True)
    speaker.speak('Ready.', 'READY')
    if not is_file and keyboard:
        def keys():
            for line in sys.stdin:
                if line.strip().lower() == 'q': stop.set(); return
                print('trigger -> analyzing' if session.trigger(time.monotonic() * 1000) else f'trigger ignored ({session.state})', flush=True)
        threading.Thread(target=keys, daemon=True).start()
        print('Serve, then press Enter. q + Enter to quit.', flush=True)
    pending = sorted(trigger_at or []); last_ts = first_ts = None; connected = True; frames = 0; t0 = time.perf_counter()
    while not stop.is_set():
        frame = source.read()
        if frame is None:
            if is_file: break
            if connected and not source.connected: session.camera_fault(False); connected = False
            continue
        if not connected:
            connected = True; speaker.speak('Camera recovered.', 'CAMERA_RECOVERED'); speaker.speak('Ready.', 'READY')
        session.add(estimator.estimate(frame)); frames += 1; last_ts = frame.timestamp_ms
        if first_ts is None: first_ts = frame.timestamp_ms
        while pending and frame.timestamp_ms >= pending[0] * 1000:
            pending.pop(0); session.trigger(frame.timestamp_ms, wait=True)
    if is_file and trigger_at is None and last_ts is not None:
        # One serve per clip: only the last window_s seconds are analyzed.
        if last_ts - first_ts > session.window_ms:
            note = (f'clip is {(last_ts - first_ts) / 1000:.1f}s but only the last {session.window_ms / 1000:.0f}s are analyzed; '
                    'record one serve per clip (or pass --trigger-at)')
            print(f'WARNING: {note}', flush=True); session.log('health', {'t': time.time(), 'event': 'clip_longer_than_window', 'note': note})
        session.trigger(last_ts, wait=True)
    while session.state != 'READY': time.sleep(0.05)
    source.close()
    summary = {'frames': frames, 'fps': frames / max(time.perf_counter() - t0, 1e-9), 'dropped': getattr(source, 'dropped', 0),
               'shots': session.results, 'session_dir': str(session.dir)}
    print(f"processed {frames} frames ({summary['fps']:.1f} fps incl. analysis); dropped {summary['dropped']}; shots {len(session.results)}", flush=True)
    for r in session.results:
        print(f"  {r['shot']}: score {r.get('score') if r.get('score') is not None else '-'} | {r['mode']}/{r['rule_id']} -> \"{r['speech']}\"", flush=True)
    return summary

def main(argv=None):
    p = argparse.ArgumentParser(prog='djoker-run', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    p.add_argument('--source', help="Override source: 'webcam', 'webcam:/dev/video0', or a video file")
    p.add_argument('--crop', help='Fixed player crop x1,y1,x2,y2; default from config (null = pose-tracked)')
    p.add_argument('--trigger-at', type=float, nargs='*', help='Video only: trigger times in seconds; default = end of clip')
    p.add_argument('--realtime', action='store_true', default=None, help='Video only: replay at recorded speed')
    p.add_argument('--serve-type', choices=['1', '2', 'unknown'])
    p.add_argument('--handedness', choices=['left', 'right', 'unknown'])
    p.add_argument('--allow-unvalidated-reference', action='store_true', default=None)
    p.add_argument('--audio', choices=['print', 'piper', 'say', 'espeak', 'wav'])
    p.add_argument('--voice', help='Piper voice .onnx (audio backend piper)')
    p.add_argument('--qwen-url'); p.add_argument('--qwen-model'); p.add_argument('--qwen-timeout', type=float)
    p.add_argument('--out', help='Output folder for runs')
    a = p.parse_args(argv)
    overrides = {'source': {'spec': a.source, 'realtime': a.realtime},
                 'pose': {'crop': [float(v) for v in a.crop.split(',')] if a.crop else None},
                 'analysis': {'serve_type': a.serve_type, 'handedness': a.handedness},
                 'reference': {'allow_unvalidated_reference': a.allow_unvalidated_reference},
                 'audio': {'backend': a.audio, 'voice': str(Path(a.voice).resolve()) if a.voice else None}, 'session': {'out_dir': str(Path(a.out).resolve()) if a.out else None},
                 'phraser': {'backend': 'qwen' if a.qwen_url else None, 'url': a.qwen_url, 'model': a.qwen_model, 'timeout_s': a.qwen_timeout}}
    run(build(load_config(a.config, overrides)), trigger_at=a.trigger_at)

if __name__ == '__main__':
    main()
