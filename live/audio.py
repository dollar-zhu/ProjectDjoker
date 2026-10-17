"""speak(text, code) -> AudioResult. Serialized, never raises: speech failure must not stop capture.

Backends: 'wav' (prerecorded audio/<CODE>.wav, played with aplay/afplay), 'say' (macOS), 'espeak' (espeak-ng), 'print'.
"""
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import threading
import time

@dataclass
class AudioResult:
    ok: bool
    backend: str
    text: str
    started_ms: float
    error: str = None

class Speaker:
    def __init__(self, backend='print', wav_dir='audio'):
        self.backend = backend; self.wav_dir = Path(wav_dir); self._lock = threading.Lock(); self._proc = None

    def _command(self, text, code):
        wav = self.wav_dir / f'{code}.wav' if code else None
        if self.backend == 'wav' and wav and wav.exists():
            player = shutil.which('aplay') or shutil.which('afplay')
            if player: return [player, str(wav)]
        if self.backend in ('say', 'wav') and shutil.which('say'): return ['say', text]
        if self.backend in ('espeak', 'wav') and shutil.which('espeak-ng'): return ['espeak-ng', text]
        return None

    def speak(self, text, code=None, wait=True):
        with self._lock:  # serialize: one utterance at a time
            started = time.monotonic() * 1000
            if self._proc and self._proc.poll() is None: self._proc.terminate()  # discard stale speech
            cmd = None if self.backend == 'print' else self._command(text, code)
            if cmd is None:
                print(f'[SPEAK] {text}', flush=True)
                return AudioResult(True, 'print', text, started)
            try:
                self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if wait: self._proc.wait(timeout=15)
                return AudioResult(True, cmd[0], text, started)
            except Exception as exc:  # noqa: BLE001 - audio must never crash the session
                print(f'[SPEAK-FAILED] {text} ({exc})', flush=True)
                return AudioResult(False, cmd[0], text, started, str(exc))
