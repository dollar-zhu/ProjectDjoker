"""Explicit Bluetooth audio routing. All inspection is read-only; no default sink changes.

Native pw-play targets stable node.name and disables fallback/reconnect. paplay is
diagnosed but not used: its CLI cannot prohibit PulseAudio stream-rescue moves.
"""
import json
import re
import shutil
import subprocess
import time


GREETING = 'lets rock and roll'


class BluetoothRoute:
    def __init__(self, address, timeout=5):
        if not isinstance(address, str) or not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', address):
            raise ValueError('Bluetooth address must be a MAC such as AA:BB:CC:DD:EE:FF')
        self.address = address.upper()
        self.timeout = float(timeout)
        if self.timeout <= 0: raise ValueError('timeout must be positive')

    def _run(self, argv):
        result = subprocess.run(argv, capture_output=True, text=True, timeout=self.timeout, check=True)
        return result.stdout

    def _matches(self, sink):
        props = sink.get('properties') or {}
        addresses = [str(props.get(key, '')).upper() for key in
                     ('api.bluez5.address', 'device.address', 'bluez.address', 'bluetooth.address', 'device.string')]
        addresses = [value for value in addresses if re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', value)]
        if addresses: return all(value == self.address for value in addresses)
        # PulseAudio's stable bluez_output/bluez_sink names encode the MAC.
        name = str(sink.get('name', ''))
        encoded = self.address.replace(':', '_')
        return bool(re.match(rf'^bluez_(?:output|sink|input|source|card)\.{encoded}(?:[.\-]|$)', name, re.I))

    @staticmethod
    def _profile(device):
        props = device.get('properties') or {}
        profile = ' '.join(str(props.get(key, '')) for key in
                           ('api.bluez5.profile', 'bluetooth.protocol', 'device.profile.name'))
        profile += ' ' + str(device.get('name', '')) + ' ' + str(device.get('active_profile', ''))
        if 'a2dp' in profile.lower(): return 'a2dp'
        if any(name in profile.lower() for name in ('hfp', 'handsfree', 'headset-head-unit', 'headset_head_unit')):
            return 'hfp'
        if 'hsp' in profile.lower() or 'headset' in profile.lower(): return 'hsp'
        return 'unknown'

    def status(self):
        state = dict(address=self.address, paired=False, connected=False, audio_ready=False,
                     error=None, sink_name=None, node_name=None, audio_profile='unknown')
        try:
            info = self._run(['bluetoothctl', 'info', self.address])
            state['paired'] = bool(re.search(r'^\s*Paired:\s*yes\s*$', info, re.M | re.I))
            state['connected'] = bool(re.search(r'^\s*Connected:\s*yes\s*$', info, re.M | re.I))
            if not state['connected']: return state
            sinks = json.loads(self._run(['pactl', '--format=json', 'list', 'sinks']))
            if not isinstance(sinks, list): raise ValueError('pactl did not return a sink list')
            matches = [s for s in sinks if isinstance(s, dict) and self._matches(s)
                       and s.get('name') and str(s.get('state', '')).upper() not in ('UNAVAILABLE', 'ERROR')]
            if len(matches) != 1:
                raise RuntimeError('selected Bluetooth audio sink missing or ambiguous')
            sink = matches[0]
            state['sink_name'] = sink['name']
            state['node_name'] = (sink.get('properties') or {}).get('node.name')
            state['audio_profile'] = self._profile(sink)
            state['audio_ready'] = bool(state['node_name'] and shutil.which('pw-play'))
            if not state['audio_ready']:
                state['error'] = ('safe playback requires pw-play and stable node.name; paplay disabled '
                                  'because PulseAudio stream rescue may move playback to a default device')
        except Exception as exc:
            state['error'] = f'{type(exc).__name__}: {exc}'
        return state

    def playback_command(self, path):
        """Recheck the selected device immediately before building a targeted player argv."""
        state = self.status()
        if not state['audio_ready']:
            raise RuntimeError(state['error'] or 'selected Bluetooth device is disconnected')
        if state['node_name'] and shutil.which('pw-play'):
            # Inhibit policy fallback if the chosen node disappears during stream creation.
            return ['pw-play', '--target', str(state['node_name']), '--properties',
                    '{"node.dont-fallback":true,"node.dont-reconnect":true}', str(path)]
        raise RuntimeError('no selected-device player available')

    def action(self, action):
        """Explicit opt-in operations only; never called by status/doctor/playback."""
        if action not in ('pair', 'trust', 'connect'): raise ValueError('unsupported Bluetooth action')
        output = self._run(['bluetoothctl', action, self.address])
        if re.search(r'\b(failed|not available|not found)\b', output, re.I):
            raise RuntimeError(output.strip())
        return output.strip()

    def doctor(self):
        """Read-only host/service capabilities, selected output profile and input sources."""
        commands = {name: bool(shutil.which(name)) for name in
                    ('bluetoothctl', 'bluetoothd', 'pipewire', 'wireplumber', 'pulseaudio',
                     'pactl', 'pw-play', 'paplay', 'systemctl', 'espeak-ng', 'say')}
        report = {'commands': commands, 'selected': self.status(), 'services': {},
                  'server': None, 'sources': [], 'cards': [], 'inspection_errors': {},
                  'pulse_fallback_safe': False}
        if commands['systemctl']:
            for service, user in (('bluetooth', False), ('pipewire', True), ('pipewire-pulse', True),
                                  ('wireplumber', True), ('pulseaudio', True)):
                argv = ['systemctl'] + (['--user'] if user else [])
                argv += ['--no-pager', 'show', '--property=LoadState,ActiveState,SubState', f'{service}.service']
                try:
                    output = self._run(argv)
                    report['services'][service] = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
                except Exception as exc:
                    report['services'][service] = {'error': f'{type(exc).__name__}: {exc}'}
        if commands['pactl']:
            for kind, argv in (
                    ('server', ['pactl', '--format=json', 'info']),
                    ('sources', ['pactl', '--format=json', 'list', 'sources']),
                    ('cards', ['pactl', '--format=json', 'list', 'cards'])):
                try:
                    value = json.loads(self._run(argv))
                    if kind == 'server':
                        report['server'] = value
                        continue
                    if not isinstance(value, list): raise ValueError(f'pactl {kind} did not return a list')
                    for device in value:
                        if not isinstance(device, dict) or not self._matches(device): continue
                        item = {'name': device.get('name'), 'audio_profile': self._profile(device)}
                        if kind == 'sources':
                            monitor = device.get('monitor_of_sink')
                            item.update(state=device.get('state'), is_monitor=(
                                str(device.get('name', '')).endswith('.monitor') or
                                monitor not in (None, 'n/a', 4294967295, '4294967295')))
                        else:
                            item.update(active_profile=device.get('active_profile'), profiles=device.get('profiles', {}))
                        report[kind].append(item)
                except Exception as exc:
                    report['inspection_errors'][kind] = f'{type(exc).__name__}: {exc}'
        return report


class SpeakerRoute:
    """Explicit opt-in (audio.route="speaker"): the worker host's current default output, e.g. a laptop speaker."""
    address = None

    def __init__(self):
        self.player = shutil.which('afplay') or shutil.which('aplay')

    def status(self):
        ready = bool(self.player)
        return dict(address=None, paired=ready, connected=ready, audio_ready=ready,
                    error=None if ready else 'host speaker needs afplay or aplay',
                    sink_name='default', node_name=None, audio_profile='speaker')

    def playback_command(self, path):
        if not self.player: raise RuntimeError('host speaker needs afplay or aplay')
        return [self.player, str(path)]


class GreetingGate:
    """One event per debounced ready transition; a transient disconnect does not re-arm."""
    def __init__(self, debounce_s=1.0, clock=time.monotonic):
        if debounce_s < 0: raise ValueError('debounce_s must be nonnegative')
        self.debounce_s = debounce_s; self.clock = clock
        self.ready = False; self._candidate = None; self._since = None

    @property
    def heart(self):
        return {'ready': self.ready, 'color': 'pink' if self.ready else 'red'}

    def update(self, ready, now=None):
        now = self.clock() if now is None else now
        ready = bool(ready)
        if ready != self._candidate:
            self._candidate = ready; self._since = now
        if ready != self.ready and now - self._since >= self.debounce_s:
            self.ready = ready
            return ready
        return False


class GreetingController:
    """Optional LED adapter implements set_ready(bool); heart is the browser fallback."""
    def __init__(self, speaker, gate=None, led=None):
        self.speaker = speaker; self.gate = gate or GreetingGate(); self.led = led
        self.led_error = None

    @property
    def heart(self): return self.gate.heart

    def update(self, ready, now=None):
        previous = self.gate.ready
        greet = self.gate.update(ready, now)
        if self.led is not None and previous != self.gate.ready:
            try: self.led.set_ready(self.gate.ready)
            except Exception as exc: self.led_error = str(exc)
        if not ready: self.speaker.cancel()
        if greet: return self.speaker.speak(GREETING, 'BLUETOOTH_READY')
        return None
