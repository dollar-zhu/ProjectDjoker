"""speak(text, code) -> AudioResult. Serialized, never raises: speech failure must not stop capture.

Backends: 'piper' (offline neural TTS, ONNX voice), 'wav' (prerecorded audio/<CODE>.wav), 'say' (macOS),
'espeak' (espeak-ng), 'print'. WAVs play with aplay/afplay. 'piper' and 'wav' fall back to say/espeak, then print.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import wave

DEFAULT_VOICE = 'en_US-joe-medium'  # CC0 voice data; ~63 MB ONNX + .onnx.json
VOICES = {'en_US-joe-medium': {'onnx_sha256': '58afce0321b8d9c46d7cdf9c16500cc55a793b4220212dba6b70fb788b3baf06', 'license': 'CC0'}}

@dataclass
class AudioResult:
    ok: bool
    backend: str
    text: str
    started_ms: float
    error: str = None

def fetch_voice(name=DEFAULT_VOICE, cache='models/piper'):
    """Download a Piper voice once into cache and verify its pinned SHA-256. Returns the .onnx path."""
    import hashlib
    cache = Path(cache); onnx = cache / f'{name}.onnx'
    if not (onnx.exists() and (cache / f'{name}.onnx.json').exists()):
        from piper.download_voices import download_voice
        cache.mkdir(parents=True, exist_ok=True); download_voice(name, cache)
    expected = VOICES.get(name, {}).get('onnx_sha256')
    if expected and hashlib.sha256(onnx.read_bytes()).hexdigest() != expected: raise ValueError(f'{onnx}: SHA-256 mismatch')
    return onnx

class Speaker:
    def __init__(self, backend='print', wav_dir='audio', voice=None):
        self.backend = backend; self.wav_dir = Path(wav_dir); self._lock = threading.Lock(); self._proc = None
        self.voice_path = voice; self.voice_error = None; self._voice = None
        self._tmp_wav = Path(tempfile.gettempdir()) / f'djoker-speech-{os.getpid()}.wav'
        if backend == 'piper': self._load_voice()  # ~0.6 s on the dev host: pay it at startup, not after the first serve

    def _load_voice(self):
        try:
            from piper import PiperVoice
            if not self.voice_path or not Path(self.voice_path).exists(): raise FileNotFoundError(f'voice not found: {self.voice_path}')
            self._voice = PiperVoice.load(str(self.voice_path))
        except Exception as exc:  # noqa: BLE001 - missing package or voice -> say/espeak/print fallback
            self.voice_error = f'{type(exc).__name__}: {exc}'
            print(f'[PIPER-UNAVAILABLE] {self.voice_error}; falling back', flush=True)

    def _piper_wav(self, text):
        try:
            with wave.open(str(self._tmp_wav), 'wb') as w: self._voice.synthesize_wav(text, w)
            return self._tmp_wav
        except Exception as exc:  # noqa: BLE001
            print(f'[PIPER-FAILED] {exc}', flush=True)
            return None

    def _command(self, text, code):
        """-> (backend label, argv) or None for print."""
        player = shutil.which('aplay') or shutil.which('afplay')
        wav = self.wav_dir / f'{code}.wav' if code else None
        if self.backend == 'wav' and wav and wav.exists() and player: return 'wav', [player, str(wav)]
        if self.backend == 'piper' and self._voice and player:
            path = self._piper_wav(text)
            if path: return 'piper', [player, str(path)]
        fallback = self.backend in ('wav', 'piper')
        if (self.backend == 'say' or fallback) and shutil.which('say'): return 'say', ['say', text]
        if (self.backend == 'espeak' or fallback) and shutil.which('espeak-ng'): return 'espeak', ['espeak-ng', text]
        return None

    def speak(self, text, code=None, wait=True):
        with self._lock:  # serialize: one utterance at a time
            started = time.monotonic() * 1000
            if self._proc and self._proc.poll() is None: self._proc.terminate(); self._proc.wait()  # discard stale speech
            found = None if self.backend == 'print' else self._command(text, code)
            if found is None:
                print(f'[SPEAK] {text}', flush=True)
                return AudioResult(True, 'print', text, started)
            label, cmd = found
            try:
                self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if wait: self._proc.wait(timeout=15)
                return AudioResult(True, label, text, started)
            except Exception as exc:  # noqa: BLE001 - audio must never crash the session
                print(f'[SPEAK-FAILED] {text} ({exc})', flush=True)
                return AudioResult(False, label, text, started, str(exc))
