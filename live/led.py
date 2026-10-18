"""Opt-in official RouterBridge RPC; never opens the reserved MCU UART."""
import socket
import time


class BrowserLED:
    capability = 'Browser pink/red heart only; onboard matrix is blue monochrome'
    error = None

    def set_ready(self, ready):
        pass


class RouterLED(BrowserLED):
    capability = 'Blue matrix heart and built-in status LED; browser heart is pink/red'

    def __init__(self, socket_path='/var/run/arduino-router.sock'):
        self.socket_path = socket_path
        self.error = None

    def set_ready(self, ready):
        try:
            import msgpack
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(.5)
                client.connect(self.socket_path)
                client.sendall(msgpack.packb([0, 1, 'djoker_audio_ready', [bool(ready)]]))
                unpacker = msgpack.Unpacker(raw=False, max_buffer_size=4096)
                deadline = time.monotonic() + .5
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Router acknowledgement timed out')
                    client.settimeout(remaining)
                    data = client.recv(1024)
                    if not data:
                        raise RuntimeError('Router closed before acknowledgement')
                    unpacker.feed(data)
                    for reply in unpacker:
                        if not isinstance(reply, list) or len(reply) != 4 or reply[:2] != [1, 1] or reply[2]:
                            raise RuntimeError('Router rejected djoker_audio_ready; install the optional sketch manually')
                        self.error = None
                        return
        except Exception as exc:
            self.error = f'LED unavailable: {exc}'


def make_led(config=None):
    config = config or {}
    return RouterLED(config.get('socket', '/var/run/arduino-router.sock')) if config.get('backend') == 'router' else BrowserLED()
