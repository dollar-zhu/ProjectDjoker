"""File IPC for the existing webcam worker; audio never owns the camera."""
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import threading
import time
import uuid

from live.conversation import LiveConversation

# sun_path is 104 bytes on macOS (108 on Linux), including the terminating NUL.
MAX_SOCKET_PATH = 103


class AudioBridge:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.session_id = str(uuid.uuid4())
        self.stop = threading.Event()
        self.socket_path = self.directory / 'audio.sock'
        self.socket_dir = None
        self.socket_path.unlink(missing_ok=True)
        if len(os.fsencode(str(self.socket_path.resolve()))) > MAX_SOCKET_PATH:
            # Deep worktree paths overflow sun_path; bind in a private (0700) short directory instead.
            self.socket_dir = Path(tempfile.mkdtemp(prefix='djoker-audio-'))
            self.socket_path = self.socket_dir / 'audio.sock'
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.socket_path))
        self.socket_path.chmod(0o600)
        self.server.listen(1)
        self.server.settimeout(.1)
        self.controller = LiveConversation.from_environment(self.session_id)
        for name in ('audio-command.json', 'utterance.wav'):
            (self.directory / name).unlink(missing_ok=True)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.mic_thread = threading.Thread(target=self._microphone, daemon=True)
        self.thread.start()
        self.mic_thread.start()

    def _microphone(self):
        while not self.stop.is_set():
            try:
                client, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with client:
                deadline = time.monotonic() + 2
                def receive(size):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Microphone upload timed out')
                    client.settimeout(remaining)
                    data = client.recv(size)
                    if not data:
                        raise ValueError('Incomplete microphone upload')
                    return data
                try:
                    header = bytearray()
                    while not header.endswith(b'\n'):
                        if len(header) >= 256:
                            raise ValueError('Invalid microphone header')
                        header.extend(receive(1))
                    metadata = json.loads(header)
                    length = metadata.get('length')
                    if (metadata.get('session_id') != self.session_id
                            or type(length) is not int or not 44 <= length <= 320044):
                        raise ValueError('Stale session or oversized microphone upload')
                    data = bytearray()
                    while len(data) < length:
                        data.extend(receive(min(65536, length - len(data))))
                    accepted = self.controller.submit_wav(bytes(data))
                    result = {'accepted': True} if accepted is not False else {'error': 'Microphone is not listening or WAV was rejected'}
                except Exception as exc:
                    result = {'error': str(exc)[:240]}
                try:
                    client.sendall(json.dumps(result).encode())
                except OSError:
                    pass

    def _run(self):
        while not self.stop.is_set():
            try:
                command = self.directory / 'audio-command.json'
                if command.exists():
                    try:
                        data = json.loads(command.read_text())
                        if data.get('session_id') == self.session_id:
                            self.controller.command(data)
                    finally:
                        command.unlink(missing_ok=True)
                state = {**self.controller.snapshot(), 'pid': os.getpid(), 'socket': str(self.socket_path.resolve()),
                         'session_id': self.session_id, 'updated': time.time()}
            except Exception as exc:
                state = {'state': 'IDLE', 'enabled': False, 'error': str(exc), 'socket': str(self.socket_path.resolve()),
                         'pid': os.getpid(), 'session_id': self.session_id, 'updated': time.time()}
            temp = self.directory / 'audio-status.tmp'
            try:
                temp.write_text(json.dumps(state, allow_nan=False))
                temp.replace(self.directory / 'audio-status.json')
            except OSError:
                pass
            self.stop.wait(.1)

    def ingest(self, *args, **kwargs):
        self.controller.ingest(*args, **kwargs)

    def close(self):
        self.stop.set()
        self.server.close()
        self.controller.close()
        self.thread.join(timeout=2)
        self.mic_thread.join(timeout=2)
        self.socket_path.unlink(missing_ok=True)
        if self.socket_dir:
            shutil.rmtree(self.socket_dir, ignore_errors=True)
        for name in ('utterance.wav', 'audio-command.json', 'audio-status.json'):
            (self.directory / name).unlink(missing_ok=True)
