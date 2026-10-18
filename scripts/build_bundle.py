"""Build an offline board bundle: dist/djoker-board-<version>[-<target>].tar.gz

Contents: djoker wheel (+ optional dependency wheels for the target), hash-verified RTMPose model and Piper voice, Djokovic board
reference table, coaching rules, board config, install/run/check scripts, licenses, BUILD_INFO.json, MANIFEST.sha256.

    .venv/bin/python scripts/build_bundle.py                                   # code + assets; deps from PyPI at install
    .venv/bin/python scripts/build_bundle.py --target-python 3.12               # + aarch64 Linux wheels -> fully offline

If local/golden/ exists (scripts/make_golden.py), it is copied into the bundle for djoker-check. It contains a real
player, so share bundles privately.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pose2d.rtmpose import fetch_model, MODELS  # noqa: E402
from live.audio import fetch_voice, DEFAULT_VOICE, VOICES  # noqa: E402

MODEL = 'rtmpose-m-body7-256x192'
SYSTEM_SPEECH = {'READY': 'Ready.', 'CAMERA_DISCONNECTED': 'Camera disconnected.', 'CAMERA_RECOVERED': 'Camera recovered.'}
BOARD_CONFIG = {
    'source': {'spec': 'webcam:/dev/video0', 'width': 1280, 'height': 720, 'realtime': False},
    'pose': {'backend': 'rtmpose-onnx', 'model': MODEL, 'cache': '../assets/models', 'provider': 'CPUExecutionProvider', 'crop': None},
    'analysis': {'window_s': 4.0, 'min_frames': 15, 'handedness': 'right', 'camera_view': 'behind_server', 'serve_type': 'unknown'},
    'reference': {'table': '../assets/reference/board_reference.json', 'rules': '../assets/coaching/rules.json',
                  'rating': '../assets/coaching/rating.json',
                  'allow_unvalidated_reference': False},
    'phraser': {'backend': 'canonical', 'url': 'http://127.0.0.1:11434/v1/chat/completions', 'model': 'qwen', 'timeout_s': 1.0},
    'audio': {'backend': 'piper', 'wav_dir': '../assets/audio', 'voice': f'../assets/voices/{DEFAULT_VOICE}.onnx'},
    'session': {'cooldown_s': 2.0, 'out_dir': '../runs'},
}
INSTALL = """#!/usr/bin/env sh
# Create .venv and install djoker. Uses only bundled wheels when dependency wheels are present (offline).
set -eu
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
"$PY" -c 'import sys; assert sys.version_info >= (3, 10), "Python >= 3.10 required, found " + sys.version'
"$PY" -m venv .venv
if ls wheels/numpy-*.whl >/dev/null 2>&1; then
  .venv/bin/pip install --no-index --find-links wheels 'djoker[tts]'
else
  .venv/bin/pip install --find-links wheels 'djoker[tts]'
fi
echo "installed. next: ./check.sh --camera webcam:/dev/video0 --speak"
"""
RUN = """#!/usr/bin/env sh
# Start the coach (webcam from config/board.json). Examples:
#   ./run.sh                                      live webcam, Enter after each serve
#   ./run.sh --source clip.mov --allow-unvalidated-reference
cd "$(dirname "$0")" && exec .venv/bin/djoker-run --config config/board.json "$@"
"""
CHECK = """#!/usr/bin/env sh
# Readiness evidence: platform, model hash, golden skeleton vs dev host, decisions, camera, audio, Qwen.
cd "$(dirname "$0")" && exec .venv/bin/djoker-check --config config/board.json "$@"
"""
README = """# Djoker board bundle {version}

1. `./install.sh` (set `PYTHON=python3.12` to choose an interpreter; needs Python >= 3.10)
2. `./check.sh --camera webcam:/dev/video0 --speak` -> writes `runs/board_check_*.json` (evidence for the release checklist)
3. `./run.sh` -> live coach; press Enter after each serve (stand-in for the button), `q` + Enter to quit.
   `./run.sh --source clip.mov` replays a saved video through the identical pipeline (labelled replay).

Configure in `config/board.json`: camera device, fixed crop, audio backend (`piper` default, `espeak`, `wav`, `print`), Qwen endpoint
(`phraser.backend: "qwen"`), and `reference.allow_unvalidated_reference` (keep false outside demos).
Prerecorded audio: put `<SPEECH_CODE>.wav` files listed in `assets/audio/speech_codes.json` into `assets/audio/` and set
`audio.backend` to `wav`.
Build: {build}
"""

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()

def git(*args):
    try: return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception: return None  # noqa: BLE001

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', type=Path, default=ROOT / 'dist')
    p.add_argument('--target-python', help='Also bundle dependency wheels for this Python (e.g. 3.12) on the target platform')
    p.add_argument('--target-platform', default='manylinux_2_28_aarch64')
    a = p.parse_args()
    version = next(l.split('"')[1] for l in (ROOT / 'pyproject.toml').read_text().splitlines() if l.startswith('version'))
    name = f'djoker-board-{version}' + (f'-py{a.target_python}-{a.target_platform}' if a.target_python else '')
    stage = a.out / name
    if stage.exists(): shutil.rmtree(stage)
    (stage / 'wheels').mkdir(parents=True)

    subprocess.run([sys.executable, '-m', 'pip', 'wheel', str(ROOT), '--no-deps', '--no-build-isolation', '-q', '-w', str(stage / 'wheels')], check=True)
    shutil.rmtree(ROOT / 'build', ignore_errors=True)
    for egg in ROOT.glob('*.egg-info'): shutil.rmtree(egg)
    if a.target_python:
        subprocess.run([sys.executable, '-m', 'pip', 'download', '-q', '--only-binary=:all:', '--python-version', a.target_python,
                        '--platform', a.target_platform, '--platform', 'manylinux2014_aarch64', '-d', str(stage / 'wheels'),
                        '-r', str(ROOT / 'requirements-board.txt')], check=True)

    model_src = fetch_model(MODEL, ROOT / 'models'); model_dst = stage / 'assets/models' / MODEL; model_dst.mkdir(parents=True)
    for f in ('end2end.onnx', 'pipeline.json', 'deploy.json', 'detail.json'): shutil.copy2(model_src / f, model_dst / f)
    assert sha256(model_dst / 'end2end.onnx') == MODELS[MODEL]['onnx_sha256']
    voice_src = fetch_voice(DEFAULT_VOICE, ROOT / 'models/piper'); (stage / 'assets/voices').mkdir(parents=True)
    for f in (voice_src, voice_src.with_suffix('.onnx.json')): shutil.copy2(f, stage / 'assets/voices' / f.name)
    (stage / 'assets/reference').mkdir(parents=True); shutil.copy2(ROOT / 'reference/projected2d/board_reference.json', stage / 'assets/reference/')
    (stage / 'assets/coaching').mkdir(parents=True); shutil.copy2(ROOT / 'coaching/rules.json', stage / 'assets/coaching/'); shutil.copy2(ROOT / 'coaching/rating.json', stage / 'assets/coaching/')
    rules = json.loads((ROOT / 'coaching/rules.json').read_text())
    speech = dict(SYSTEM_SPEECH, **{r['speech_code']: r['canonical_speech'] for r in rules['rules']})
    (stage / 'assets/audio').mkdir(parents=True)
    (stage / 'assets/audio/speech_codes.json').write_text(json.dumps(speech, indent=2) + '\n')
    golden = ROOT / 'local/golden'  # private fixtures (real player); never in git, copied only into local bundles
    has_golden = (golden / 'expected_pose.json').exists()
    if has_golden: shutil.copytree(golden, stage / 'golden', ignore=shutil.ignore_patterns('__pycache__'))
    (stage / 'config').mkdir(); (stage / 'config/board.json').write_text(json.dumps(dict(BOARD_CONFIG, check={'golden_dir': '../golden'}), indent=2) + '\n')
    (stage / 'licenses').mkdir()
    shutil.copy2(ROOT / 'DATA_LICENSE', stage / 'licenses/DATA_LICENSE-tennis-serve-dataset-CC-BY-4.0')
    (stage / 'licenses/MODEL_NOTICE.txt').write_text(
        f"RTMPose-m body7 256x192 ONNX from OpenMMLab MMPose (Apache-2.0).\nSource: {MODELS[MODEL]['url']}\n"
        f"SHA-256 (end2end.onnx): {MODELS[MODEL]['onnx_sha256']}\n"
        f"Piper voice {DEFAULT_VOICE} (voice data {VOICES[DEFAULT_VOICE]['license']}) from https://huggingface.co/rhasspy/piper-voices\n"
        f"SHA-256 ({DEFAULT_VOICE}.onnx): {VOICES[DEFAULT_VOICE]['onnx_sha256']}\n"
        "Speech runtime piper-tts (GPL-3.0-or-later, https://github.com/OHF-Voice/piper1-gpl) is installed from its own wheel.\n")
    for fname, text in (('install.sh', INSTALL), ('run.sh', RUN), ('check.sh', CHECK)):
        (stage / fname).write_text(text); (stage / fname).chmod(0o755)
    build = {'version': version, 'built': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'git_commit': git('rev-parse', 'HEAD'),
             'git_dirty': bool(git('status', '--porcelain')), 'builder_python': sys.version.split()[0],
             'target': {'python': a.target_python, 'platform': a.target_platform} if a.target_python else 'deps from PyPI at install',
             'model': {'name': MODEL, 'onnx_sha256': MODELS[MODEL]['onnx_sha256']},
             'voice': {'name': DEFAULT_VOICE, 'onnx_sha256': VOICES[DEFAULT_VOICE]['onnx_sha256']},
             'reference_validation': json.loads((ROOT / 'reference/projected2d/board_reference.json').read_text())['validation']['status'],
             'rules': {'version': rules['version'], 'status': rules['status']}, 'golden_fixtures': 'included (private)' if has_golden else 'absent',
             'rating': {k: json.loads((ROOT / 'coaching/rating.json').read_text())[k] for k in ('version', 'status')}}
    (stage / 'BUILD_INFO.json').write_text(json.dumps(build, indent=2) + '\n')
    (stage / 'README.md').write_text(README.format(version=version, build=json.dumps(build)))
    files = sorted(f for f in stage.rglob('*') if f.is_file())
    (stage / 'MANIFEST.sha256').write_text(''.join(f'{sha256(f)}  {f.relative_to(stage)}\n' for f in files))
    archive = a.out / f'{name}.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar: tar.add(stage, arcname=name)
    print(json.dumps({'bundle': str(archive), 'size_mb': round(archive.stat().st_size / 1e6, 1), 'files': len(files) + 1,
                      'git_dirty': build['git_dirty']}, indent=1))

if __name__ == '__main__':
    main()
