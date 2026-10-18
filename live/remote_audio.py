"""Piper on Ventuno, controlled through a loopback-only ADB port forward.

Run on the board: python -m live.remote_audio --address MAC --voice model.onnx
Forward on the Mac: adb -s SERIAL forward tcp:18877 tcp:18877
Set audio.remote_url to http://127.0.0.1:18877 in the private audio config.
"""
import argparse
from collections import deque
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import urllib.parse
import urllib.request
import uuid

from .audio import AudioResult, Speaker
from .bluetooth import BluetoothRoute


class RemoteRoute:
    def __init__(self, url, address, timeout=3):
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1')
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/')):
            raise ValueError('Remote audio requires an HTTP loopback ADB forward')
        self.address = BluetoothRoute(address).address
        self.url = url.rstrip('/'); self.timeout = timeout

    def request(self, path, data=None, timeout=None):
        body = None if data is None else json.dumps(data).encode()
        request = urllib.request.Request(self.url + path, data=body,
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
            result = json.loads(response.read(16384))
        if not isinstance(result, dict): raise ValueError('Invalid board audio response')
        return result

    def status(self):
        try:
            state = self.request('/status')
            if state.get('address') != self.address:
                raise ValueError('Board audio service is configured for a different headset')
            return state
        except Exception as exc:
            return dict(address=self.address, paired=False, connected=False, audio_ready=False,
                        error=f'Ventuno audio unavailable: {exc}')


class RemoteSpeaker:
    """Cancellation IDs also reject a request that reaches the board after cancel."""
    def __init__(self, route):
        self.route = route; self._lock = threading.Lock(); self._generation = 0
        self._active = None; self._closed = False

    def cancellation_token(self):
        with self._lock: return self._generation

    def cancel(self):
        with self._lock:
            self._generation += 1; request_id = self._active
        if request_id: self.route.request('/cancel', {'id': request_id})

    def close(self):
        with self._lock: self._closed = True
        self.cancel()

    def speak(self, text, code=None, wait=True, cancellation_token=None):
        started = time.monotonic() * 1000; request_id = None
        try:
            with self._lock:
                if self._closed or (cancellation_token is not None and cancellation_token != self._generation):
                    raise RuntimeError('speech cancelled')
                if self._active: raise RuntimeError('speech already active')
                request_id = self._active = str(uuid.uuid4())
            state = self.route.status()
            if not state.get('audio_ready'): raise RuntimeError(state.get('error') or 'Headphones disconnected')
            result = self.route.request('/speak', {'id': request_id, 'text': text, 'code': code}, timeout=25)
            return AudioResult(bool(result.get('ok')), 'piper-ventuno', text, started, result.get('error'))
        except Exception as exc:
            if request_id:
                try: self.route.request('/cancel', {'id': request_id})
                except Exception: pass
            return AudioResult(False, 'piper-ventuno', text, started, str(exc))
        finally:
            with self._lock:
                if request_id and self._active == request_id: self._active = None


class AudioService:
    def __init__(self, speaker, route):
        self.speaker = speaker; self.route = route; self._lock = threading.Lock()
        self._active = None; self._cancelled = deque(maxlen=256)

    def cancel(self, request_id):
        with self._lock:
            self._cancelled.append(request_id)
            if self._active == request_id: self.speaker.cancel()
        return {'ok': True}

    def speak(self, request_id, text, code=None):
        with self._lock:
            if request_id in self._cancelled: return {'ok': False, 'error': 'speech cancelled'}
            if self._active: return {'ok': False, 'error': 'board speech already active'}
            self._active = request_id; token = self.speaker.cancellation_token()
        try:
            return asdict(self.speaker.speak(text, code=code, cancellation_token=token))
        finally:
            with self._lock: self._active = None


def make_server(service, port=18877):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass  # Do not log spoken text.

        def reply(self, data, status=200):
            body = json.dumps(data).encode()
            self.send_response(status); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers()
            try: self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError): pass

        def do_GET(self):
            if self.path != '/status': return self.reply({'error': 'Not found'}, 404)
            self.reply(service.route.status())

        def do_POST(self):
            try:
                self.connection.settimeout(3)
                if self.headers.get('Origin'): raise ValueError('Browser requests are not accepted')
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096: raise ValueError('Invalid request size')
                data = json.loads(self.rfile.read(size))
                request_id = data.get('id')
                if not isinstance(request_id, str) or not 1 <= len(request_id) <= 64:
                    raise ValueError('Invalid request ID')
                if self.path == '/cancel': return self.reply(service.cancel(request_id))
                if self.path != '/speak': return self.reply({'error': 'Not found'}, 404)
                text = data.get('text'); code = data.get('code')
                if not isinstance(text, str) or not 1 <= len(text) <= 500: raise ValueError('Invalid speech text')
                if code is not None and (not isinstance(code, str) or not code.replace('_', '').isalnum()):
                    raise ValueError('Invalid speech code')
                self.reply(service.speak(request_id, text, code))
            except Exception as exc:
                self.reply({'ok': False, 'error': str(exc)}, 400)
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address', required=True); parser.add_argument('--voice', required=True)
    parser.add_argument('--port', type=int, default=18877)
    args = parser.parse_args()
    route = BluetoothRoute(args.address)
    with Speaker('piper', voice=args.voice, route=route) as speaker:
        if speaker.voice_error: raise RuntimeError(speaker.voice_error)
        server = make_server(AudioService(speaker, route), args.port)
        try: server.serve_forever()
        finally: server.server_close()


if __name__ == '__main__': main()
