"""Optional, lazy English ASR. Audio stays in memory; no microphone is opened here.

``python -m live.asr known.wav --model /path/to/faster-whisper-model``
requires an independently installed faster-whisper runtime (optional version
1.2.1). The default is a local model directory. An explicit CLI model name may download
weights; configured live ASR only accepts local model directories.
"""
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import threading
import wave

import numpy as np


MAX_SECONDS = 10
SAMPLE_RATE = 16000
MAX_WAV_BYTES = SAMPLE_RATE * 2 * MAX_SECONDS + 4096
DEFAULT_MODEL_PATH = 'models/faster-whisper-tiny.en'


def decode_wav(data):
    """Validate bounded mono PCM16/16 kHz WAV bytes and return float32 samples."""
    if not isinstance(data, bytes) or not 44 <= len(data) <= MAX_WAV_BYTES:
        raise ValueError('Expected at most 10 seconds of mono PCM16/16 kHz WAV bytes')
    try:
        with wave.open(io.BytesIO(data), 'rb') as wav:
            frames = wav.getnframes()
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (
                    1, 2, SAMPLE_RATE, 'NONE'):
                raise ValueError('WAV must be uncompressed mono PCM16 at 16000 Hz')
            if not 0 < frames <= SAMPLE_RATE * MAX_SECONDS:
                raise ValueError('WAV duration must be greater than zero and at most 10 seconds')
            pcm = wav.readframes(frames)
            if len(pcm) != frames * 2:
                raise ValueError('Truncated WAV audio')
    except (wave.Error, EOFError) as exc:
        raise ValueError('Invalid WAV audio') from exc
    return np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0


class EnglishASR:
    """One persistent model, initialized only inside transcribe's worker thread.

    ``model_path`` is an external local directory (``~`` is expanded), never a
    download ID. ``model`` also accepts directories. Named downloads require
    explicit ``allow_download``; the known-WAV CLI opts in for explicit names.
    """

    def __init__(self, config=None):
        self.config = dict(config or {})
        self.enabled = bool(self.config.get('enabled', bool(self.config)))
        self._model = None
        self._lock = threading.Lock()
        self._status = {
            'enabled': self.enabled, 'loaded': False,
            'available': None,
            'runtime': 'faster-whisper', 'error': None if self.enabled else 'ASR is not configured',
        }

    def check_runtime(self):
        """Cheap availability probe for the ASR worker, without importing/loading a model."""
        if not self.enabled:
            return False
        try:
            available = importlib.util.find_spec('faster_whisper') is not None
        except (ImportError, ValueError):
            available = False
        with self._lock:
            self._status['available'] = available
            self._status['error'] = None if available else 'Optional faster-whisper runtime is not installed'
        return available

    def snapshot(self):
        with self._lock:
            return dict(self._status)

    def _model_source(self):
        raw = str(self.config.get('model_path') or self.config.get('model', DEFAULT_MODEL_PATH))
        expanded = os.path.expandvars(os.path.expanduser(raw))
        path = Path(expanded)
        if (not self.config.get('allow_download', False) or self.config.get('model_path')
                or '/' in expanded or raw.startswith(('/', '.', '~'))
                or path.exists()):
            if not path.is_dir():
                raise FileNotFoundError(f'ASR model directory does not exist: {expanded}')
            return str(path.resolve())
        return raw

    def transcribe(self, wav_bytes):
        samples = decode_wav(wav_bytes)
        if not self.enabled:
            raise RuntimeError('ASR is not configured')
        try:
            if self._model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise RuntimeError('Optional faster-whisper runtime is not installed') from exc
                self._model = WhisperModel(
                    self._model_source(),
                    device=self.config.get('device', 'cpu'),
                    compute_type=self.config.get('compute_type', 'int8'),
                )
                with self._lock:
                    self._status['loaded'] = True
                    self._status['available'] = True
            segments, _ = self._model.transcribe(
                samples, language='en', beam_size=1, vad_filter=False,
                condition_on_previous_text=False,
            )
            text = ' '.join(segment.text.strip() for segment in segments).strip()[:500]
            with self._lock:
                self._status['error'] = None
            return text
        except Exception as exc:
            with self._lock:
                self._status['error'] = str(exc)[:240]
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wav')
    parser.add_argument('--model', default=DEFAULT_MODEL_PATH,
                        help='Local model directory (default), or explicit model name (may download)')
    args = parser.parse_args(argv)
    asr = EnglishASR({'enabled': True, 'model': args.model, 'allow_download': True})
    try:
        with open(args.wav, 'rb') as handle:
            data = handle.read(MAX_WAV_BYTES + 1)
        print(json.dumps({'transcript': asr.transcribe(data), 'asr': asr.snapshot()}))
        return 0
    except Exception as exc:
        print(json.dumps({'error': str(exc), 'asr': asr.snapshot()}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
