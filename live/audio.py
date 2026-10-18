"""speak(text, code) -> AudioResult. Serialized, never raises: speech failure must not stop capture.

Backends: 'piper' (offline neural TTS, ONNX voice), 'wav' (prerecorded audio/<CODE>.wav), 'say' (macOS),
'espeak' (espeak-ng), 'print'. WAVs play with aplay/afplay. 'piper' and 'wav' fall back to say/espeak, then print.
An explicit route supplies playback_command(path) -> argv or raises; it never uses host playback fallback.
cancel() does not wait on synthesis. close() releases cached greeting WAVs; ordinary WAVs are removed after playback.
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
    def __init__(self, backend='print', wav_dir='audio', voice=None, route=None, timeout=15):
        self.backend = backend; self.wav_dir = Path(wav_dir); self._lock = threading.Lock(); self._proc = None
        self.voice_path = voice; self.voice_error = None; self._voice = None
        self.route = route; self.timeout = float(timeout)
        if self.timeout <= 0: raise ValueError('timeout must be positive')
        self._state_lock = threading.Lock(); self._generation = 0; self._closed = False
        self._owned = set(); self._cache = {}
        self._tmp_wav = None; self._temp_dir = None
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
        path = self._new_wav()
        try:
            with wave.open(str(path), 'wb') as w: self._voice.synthesize_wav(text, w)
            return path
        except Exception as exc:  # noqa: BLE001
            self._remove(path)
            print(f'[PIPER-FAILED] {exc}', flush=True)
            return None

    def _new_wav(self):
        # TemporaryDirectory/mkstemp enforce private modes and exclusive ownership.
        if self._temp_dir is None:
            self._temp_dir = tempfile.TemporaryDirectory(prefix='djoker-audio-')
        fd, name = tempfile.mkstemp(prefix='speech-', suffix='.wav', dir=self._temp_dir.name)
        os.close(fd)
        path = Path(name)
        self._owned.add(path); self._tmp_wav = path
        return path

    def _remove(self, path):
        if path in self._owned:
            path.unlink(missing_ok=True); self._owned.discard(path)

    @staticmethod
    def _stop(proc):
        if proc is None: return
        try:
            if proc.poll() is not None: return
            proc.terminate()
            try: proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def cancel(self):
        """Cancel playback without acquiring the (possibly synthesizing) speech lock."""
        with self._state_lock:
            self._generation += 1
            proc = self._proc
        self._stop(proc)

    def cancellation_token(self):
        """Reserve the current cancellation generation before dispatching queued speech."""
        with self._state_lock: return self._generation

    def close(self):
        with self._state_lock: self._closed = True
        self.cancel()
        with self._lock:
            for path in tuple(self._owned): self._remove(path)
            self._cache.clear()
            if self._temp_dir is not None:
                self._temp_dir.cleanup(); self._temp_dir = None

    def __enter__(self): return self

    def __exit__(self, *args): self.close()

    def synthesize(self, text, output):
        """Write native Piper output without playing it. Caller owns output."""
        with self._lock:
            if self._closed: raise RuntimeError('speaker is closed')
            if self._voice is None: raise RuntimeError(self.voice_error or 'Piper voice not loaded')
            with wave.open(str(output), 'wb') as wav: self._voice.synthesize_wav(text, wav)
        return Path(output)

    def _render(self, text):
        if self.backend == 'piper' and self._voice:
            path = self._piper_wav(text)
            if path: return 'piper', path
        path = self._new_wav()
        try:
            if shutil.which('espeak-ng'):
                cmd = ['espeak-ng', '-w', str(path), text]
            elif shutil.which('say'):
                cmd = ['say', '--file-format=WAVE', '-o', str(path), text]
            else:
                raise RuntimeError('no WAV speech synthesizer available for selected route')
            proc = self._start(cmd)
            self._wait(proc)
            return 'espeak' if cmd[0] == 'espeak-ng' else 'say', path
        except Exception:
            self._remove(path)
            raise

    def _command(self, text, code):
        """-> (backend label, argv) or None for print."""
        if self.route is not None:
            wav = self.wav_dir / f'{code}.wav' if code else None
            if wav and wav.is_file() and self.backend in ('wav', 'piper'):
                label, path = 'wav', wav
            elif text == 'lets rock and roll' and text in self._cache:
                label, path = self._cache[text]
            else:
                label, path = self._render(text)
                if text == 'lets rock and roll': self._cache[text] = (label, path)
            return label, self.route.playback_command(path)
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

    def _start(self, cmd):
        with self._state_lock:
            if self._closed or self._active_generation != self._generation:
                raise RuntimeError('speech cancelled')
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._proc = proc
            return proc

    def _wait(self, proc):
        try:
            code = proc.wait(timeout=self.timeout)
            if code: raise RuntimeError(f'audio process exited with status {code}')
        except Exception:
            self._stop(proc)
            raise
        finally:
            with self._state_lock:
                if self._proc is proc: self._proc = None

    def _finish_async(self, proc, paths):
        try: self._wait(proc)
        except Exception: pass
        finally:
            with self._lock:
                for path in paths: self._remove(path)

    def speak(self, text, code=None, wait=True, cancellation_token=None):
        with self._lock:  # serialize: one utterance at a time
            started = time.monotonic() * 1000
            label = self.backend; proc = None; asynchronous = False
            before = set(self._owned)
            try:
                with self._state_lock:
                    if self._closed: raise RuntimeError('speaker is closed')
                    self._active_generation = self._generation if cancellation_token is None else cancellation_token
                    if self._active_generation != self._generation: raise RuntimeError('speech cancelled')
                    previous = self._proc
                self._stop(previous)
                found = None if self.backend == 'print' else self._command(text, code)
                if found is None:
                    if self.route is not None: raise RuntimeError('selected route requires audible output')
                    print(f'[SPEAK] {text}', flush=True)
                    return AudioResult(True, 'print', text, started)
                label, cmd = found
                proc = self._start(cmd)
                if wait:
                    self._wait(proc)
                    with self._state_lock:
                        if self._generation != self._active_generation: raise RuntimeError('speech cancelled')
                else:
                    paths = self._owned - before - {p for _, p in self._cache.values()}
                    threading.Thread(target=self._finish_async, args=(proc, paths), daemon=True).start()
                    asynchronous = True
                return AudioResult(True, label, text, started)
            except Exception as exc:  # noqa: BLE001 - audio must never crash the session
                with self._state_lock: active = proc is not None and self._proc is proc
                if active: self._stop(proc)
                print(f'[SPEAK-FAILED] {text} ({exc})', flush=True)
                return AudioResult(False, label, text, started, str(exc))
            finally:
                if not asynchronous:
                    for path in self._owned - before - {p for _, p in self._cache.values()}: self._remove(path)
