import io
import errno
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
import wave

from live.audio import Speaker
from live.audio_check import main
from live.bluetooth import BluetoothRoute, GREETING, GreetingController, GreetingGate


ADDRESS = 'AA:BB:CC:DD:EE:FF'
SINK = 'bluez_output.AA_BB_CC_DD_EE_FF.1'


def sinks(address=ADDRESS, node=True):
    props = {'api.bluez5.address': address}
    if node: props['node.name'] = SINK
    return [{'name': SINK, 'state': 'SUSPENDED', 'properties': props}]


def process(code=0):
    proc = mock.Mock()
    proc.poll.return_value = None
    proc.wait.return_value = code
    return proc


def synthesize(text, output):
    output.setnchannels(1); output.setsampwidth(2); output.setframerate(22050)
    output.writeframes(b'\0\0' * 20)


class BluetoothTests(unittest.TestCase):
    def route(self, connected=True, paired=True, devices=None):
        route = BluetoothRoute(ADDRESS)
        route._run = mock.Mock(side_effect=[
            f"Paired: {'yes' if paired else 'no'}\nConnected: {'yes' if connected else 'no'}\n",
            json.dumps(sinks() if devices is None else devices)])
        return route

    def test_mac_validation_rejects_shell_and_option_input(self):
        for address in ('--help', 'AA:BB:CC:DD:EE:FF; reboot', '', 'AA_BB_CC_DD_EE_FF'):
            with self.assertRaises(ValueError): BluetoothRoute(address)
        self.assertEqual(BluetoothRoute(ADDRESS.lower()).address, ADDRESS)

    def test_paired_is_not_connected_or_audio_ready(self):
        state = self.route(connected=False).status()
        self.assertTrue(state['paired'])
        self.assertFalse(state['connected']); self.assertFalse(state['audio_ready'])

    @mock.patch('live.bluetooth.shutil.which', return_value='/bin/tool')
    def test_stable_node_target_and_unsafe_pulse_rejected(self, which):
        self.assertEqual(self.route().playback_command('a.wav'),
                         ['pw-play', '--target', SINK, '--properties',
                          '{"node.dont-fallback":true,"node.dont-reconnect":true}', 'a.wav'])
        with self.assertRaisesRegex(RuntimeError, 'paplay disabled'):
            self.route(devices=sinks(node=False)).playback_command('a.wav')

    @mock.patch('live.bluetooth.shutil.which', side_effect=lambda name: '/bin/paplay' if name == 'paplay' else None)
    def test_paplay_when_pw_play_is_missing(self, which):
        with self.assertRaisesRegex(RuntimeError, 'stream rescue'):
            self.route().playback_command('a.wav')

    def test_no_wrong_device_or_ambiguous_sink_fallback(self):
        wrong = [{'name': 'bluez_output.11_22_33_44_55_66.1',
                  'properties': {'api.bluez5.address': '11:22:33:44:55:66'}}]
        conflicting = sinks(address='11:22:33:44:55:66')
        for devices in ([], wrong, conflicting, sinks() + sinks()):
            with self.assertRaises(RuntimeError): self.route(devices=devices).playback_command('a.wav')

    def test_name_discovery_without_address_properties(self):
        route = self.route(devices=[{'name': SINK, 'properties': {}}])
        with mock.patch('live.bluetooth.shutil.which', return_value='paplay'):
            state = route.status()
            self.assertEqual(state['sink_name'], SINK)
            self.assertFalse(state['audio_ready'])

    def test_connected_without_sink_not_audio_ready(self):
        state = self.route(devices=[]).status()
        self.assertTrue(state['connected']); self.assertFalse(state['audio_ready'])
        self.assertIn('missing', state['error'])

    def test_subprocess_timeout_is_read_only_and_reported(self):
        route = BluetoothRoute(ADDRESS, timeout=0.1)
        with mock.patch('live.bluetooth.subprocess.run', side_effect=subprocess.TimeoutExpired('bluetoothctl', .1)) as run:
            self.assertIn('TimeoutExpired', route.doctor()['selected']['error'])
        self.assertEqual(run.call_args_list[0].args[0], ['bluetoothctl', 'info', ADDRESS])
        for call in run.call_args_list:
            self.assertEqual(call.kwargs['timeout'], .1)
            self.assertNotIn('shell', call.kwargs)

    def test_doctor_never_mutates_and_actions_are_explicit(self):
        route = BluetoothRoute(ADDRESS)
        with mock.patch.object(route, '_run', return_value='Paired: yes\nConnected: no') as run:
            route.doctor()
            self.assertEqual(run.call_args_list[0].args[0], ['bluetoothctl', 'info', ADDRESS])
            route.action('connect')
            self.assertEqual(run.call_args.args[0], ['bluetoothctl', 'connect', ADDRESS])
            with self.assertRaises(ValueError): route.action('remove')

    @mock.patch('live.bluetooth.shutil.which', return_value='/bin/tool')
    def test_doctor_services_sources_and_profiles_are_read_only(self, which):
        route = BluetoothRoute(ADDRESS)
        output = sinks()
        output[0]['properties']['api.bluez5.profile'] = 'a2dp-sink'
        sources = [
            {'name': 'bluez_input.AA_BB_CC_DD_EE_FF.0', 'state': 'RUNNING',
             'properties': {'device.address': ADDRESS, 'api.bluez5.profile': 'headset-head-unit'}},
            {'name': SINK + '.monitor', 'monitor_of_sink': 2, 'properties': {'device.address': ADDRESS}}]
        card = {'name': 'bluez_card.AA_BB_CC_DD_EE_FF', 'properties': {'device.string': ADDRESS},
                'active_profile': 'a2dp-sink', 'profiles': {'a2dp-sink': {}, 'headset-head-unit': {}}}
        def run(argv):
            if argv[0] == 'bluetoothctl': return 'Paired: yes\nConnected: yes'
            if argv[0] == 'systemctl':
                self.assertIn('show', argv)
                return 'LoadState=loaded\nActiveState=active\nSubState=running\n'
            if argv[-1] == 'sinks': return json.dumps(output)
            if argv[-1] == 'info': return json.dumps({'server_name': 'PulseAudio (on PipeWire 1.2)'})
            if argv[-1] == 'sources': return json.dumps(sources)
            if argv[-1] == 'cards': return json.dumps([card])
            self.fail(f'unexpected command: {argv}')
        with mock.patch.object(route, '_run', side_effect=run) as invoked:
            report = route.doctor()
        self.assertEqual(report['selected']['audio_profile'], 'a2dp')
        self.assertEqual(report['sources'][0]['audio_profile'], 'hfp')
        self.assertFalse(report['sources'][0]['is_monitor'])
        self.assertTrue(report['sources'][1]['is_monitor'])
        self.assertEqual(report['cards'][0]['active_profile'], 'a2dp-sink')
        self.assertEqual(report['services']['wireplumber']['ActiveState'], 'active')
        self.assertFalse(report['pulse_fallback_safe'])
        for call in invoked.call_args_list:
            self.assertTrue(call.args[0][0] in ('bluetoothctl', 'systemctl', 'pactl'))
            self.assertFalse(set(call.args[0]) & {'pair', 'trust', 'connect', 'start', 'restart', 'enable'})

    def test_disconnect_is_rechecked_for_every_playback(self):
        route = self.route()
        with mock.patch('live.bluetooth.shutil.which', return_value='tool'):
            route.playback_command('a.wav')
            route._run.side_effect = ['Paired: yes\nConnected: no']
            with self.assertRaises(RuntimeError): route.playback_command('a.wav')

    def test_invalid_json_and_missing_tools_fail_closed(self):
        route = self.route()
        route._run.side_effect = ['Connected: yes', 'not JSON']
        self.assertIn('JSONDecodeError', route.status()['error'])
        with mock.patch('live.bluetooth.shutil.which', return_value=None):
            with self.assertRaises(RuntimeError): self.route().playback_command('a.wav')


class SpeakerTests(unittest.TestCase):
    def setUp(self):
        # Tests explicitly isolate creation locally; runtime uses the system temp default.
        temp_root = mock.patch('live.audio.tempfile.tempdir', str(Path.cwd()))
        temp_root.start()
        self.addCleanup(temp_root.stop)

    def speaker(self, route=None):
        speaker = Speaker('print', route=route, timeout=.1)
        speaker.backend = 'piper'
        speaker._voice = mock.Mock()
        speaker._voice.synthesize_wav.side_effect = synthesize
        self.addCleanup(speaker.close)
        return speaker

    @mock.patch('live.audio.subprocess.Popen')
    def test_unique_temp_files_and_cleanup(self, popen):
        popen.return_value = process()
        route = mock.Mock()
        route.playback_command.side_effect = lambda path: ['player', str(path)]
        first, second = self.speaker(route), self.speaker(route)
        self.assertTrue(first.speak('one').ok)
        self.assertTrue(second.speak('two').ok)
        self.assertNotEqual(first._tmp_wav, second._tmp_wav)
        self.assertFalse(first._tmp_wav.exists()); self.assertFalse(second._tmp_wav.exists())

    @mock.patch('live.audio.subprocess.Popen')
    def test_timeout_terminates_kills_reaps_and_cleans(self, popen):
        proc = process()
        proc.wait.side_effect = [subprocess.TimeoutExpired('player', .1),
                                 subprocess.TimeoutExpired('player', 1), 0]
        popen.return_value = proc
        route = mock.Mock(); route.playback_command.return_value = ['player']
        speaker = self.speaker(route)
        self.assertFalse(speaker.speak('timeout').ok)
        proc.terminate.assert_called_once(); proc.kill.assert_called_once()
        self.assertFalse(speaker._tmp_wav.exists())

    @mock.patch('live.audio.subprocess.Popen')
    def test_cancel_is_independent_while_synthesis_holds_speak_lock(self, popen):
        entered, release = threading.Event(), threading.Event()
        route = mock.Mock(); route.playback_command.return_value = ['player']
        speaker = self.speaker(route)
        def blocking_synth(text, output):
            entered.set()
            self.assertTrue(release.wait(2))
            synthesize(text, output)
        speaker._voice.synthesize_wav.side_effect = blocking_synth
        results = []
        thread = threading.Thread(target=lambda: results.append(speaker.speak('cancel')))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            canceller = threading.Thread(target=speaker.cancel)
            canceller.start(); canceller.join(.5)
            self.assertFalse(canceller.is_alive(), 'cancel must not wait for the speech lock')
        finally:
            release.set(); thread.join(2)
        self.assertFalse(results[0].ok)
        popen.assert_not_called()
        self.assertFalse(speaker._tmp_wav.exists())

    @mock.patch('live.audio.subprocess.Popen')
    def test_cancel_stops_active_playback(self, popen):
        entered, stopped = threading.Event(), threading.Event()
        proc = process()
        def wait(timeout):
            entered.set()
            self.assertTrue(stopped.wait(2))
            return -15
        proc.wait.side_effect = wait
        proc.terminate.side_effect = stopped.set
        popen.return_value = proc
        route = mock.Mock(); route.playback_command.return_value = ['player']
        speaker = self.speaker(route)
        results = []
        thread = threading.Thread(target=lambda: results.append(speaker.speak('hello')))
        thread.start()
        try:
            self.assertTrue(entered.wait(2)); speaker.cancel()
        finally:
            stopped.set(); thread.join(2)
        self.assertFalse(results[0].ok)
        self.assertFalse(speaker._tmp_wav.exists())

    @mock.patch('live.audio.subprocess.Popen')
    def test_route_error_never_uses_host_fallback(self, popen):
        route = mock.Mock(); route.playback_command.side_effect = RuntimeError('disconnected')
        speaker = self.speaker(route)
        with mock.patch('live.audio.shutil.which', return_value='host-player'):
            result = speaker.speak('wrong device forbidden')
        self.assertFalse(result.ok); popen.assert_not_called()
        self.assertFalse(speaker._tmp_wav.exists())

    @mock.patch('live.audio.subprocess.Popen', side_effect=FileNotFoundError('missing player'))
    def test_player_start_failure_cleans_temp(self, popen):
        route = mock.Mock(); route.playback_command.return_value = ['player']
        speaker = self.speaker(route)
        self.assertFalse(speaker.speak('missing').ok)
        self.assertFalse(speaker._tmp_wav.exists())

    @mock.patch('live.audio.subprocess.Popen')
    def test_nonzero_exit_is_failure(self, popen):
        popen.return_value = process(1)
        route = mock.Mock(); route.playback_command.return_value = ['player']
        self.assertFalse(self.speaker(route).speak('failure').ok)

    @mock.patch('live.audio.subprocess.Popen')
    def test_greeting_wave_is_cached_until_close(self, popen):
        popen.return_value = process()
        route = mock.Mock(); route.playback_command.return_value = ['player']
        speaker = self.speaker(route)
        speaker.speak(GREETING, 'BLUETOOTH_READY'); path = speaker._tmp_wav
        speaker.speak(GREETING, 'ARBITRARY_CODE')
        self.assertTrue(path.exists())
        speaker._voice.synthesize_wav.assert_called_once()
        speaker.close(); self.assertFalse(path.exists())

    @mock.patch('live.audio.subprocess.Popen')
    def test_async_playback_keeps_wave_until_reaped(self, popen):
        started, release = threading.Event(), threading.Event()
        proc = process()
        def wait(timeout):
            started.set()
            self.assertTrue(release.wait(2))
            return 0
        proc.wait.side_effect = wait
        popen.return_value = proc
        route = mock.Mock(); route.playback_command.return_value = ['player']
        speaker = self.speaker(route)
        try:
            self.assertTrue(speaker.speak('async', wait=False).ok)
            self.assertTrue(started.wait(2)); path = speaker._tmp_wav
            self.assertTrue(path.exists())
        finally:
            release.set()
        # close joins the serialized cleanup path; both operations only delete owned paths.
        speaker.close()
        self.assertFalse(path.exists())

    def test_native_synthesis_output_uses_piper_voice(self):
        speaker = self.speaker()
        path = Path(f'.audio-test-{id(self)}.wav')
        self.addCleanup(path.unlink, missing_ok=True)
        speaker.synthesize('native', path)
        with wave.open(str(path)) as wav: self.assertEqual(wav.getnframes(), 20)
        self.assertNotIn(path, speaker._owned)

    def test_private_per_speaker_directories_and_files_removed_at_close(self):
        first, second = self.speaker(), self.speaker()
        with mock.patch('live.audio.tempfile.TemporaryDirectory', wraps=tempfile.TemporaryDirectory) as created:
            first_path = first._piper_wav('first')
            created.assert_called_once_with(prefix='djoker-audio-')
        second_path = second._piper_wav('second')
        self.assertNotEqual(first_path.parent, second_path.parent)
        self.assertEqual(first_path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(first_path.stat().st_mode & 0o777, 0o600)
        directory = first_path.parent
        first.close()
        self.assertFalse(directory.exists())
        self.assertTrue(second_path.exists())

    def test_cancel_tolerates_process_already_exited_esrch_races(self):
        for operation in ('poll', 'terminate', 'wait'):
            speaker = self.speaker()
            proc = process()
            getattr(proc, operation).side_effect = ProcessLookupError(errno.ESRCH, 'process exited')
            speaker._proc = proc
            speaker.cancel()
            self.assertEqual(speaker._generation, 1)

    @mock.patch('live.audio.subprocess.Popen')
    def test_stale_cancellation_token_before_speak_never_synthesizes_or_plays(self, popen):
        route = mock.Mock(); route.playback_command.return_value = ['player']
        speaker = self.speaker(route)
        token = speaker.cancellation_token()
        speaker.cancel()
        result = speaker.speak('stale dispatch', cancellation_token=token)
        self.assertFalse(result.ok)
        self.assertIn('cancelled', result.error)
        speaker._voice.synthesize_wav.assert_not_called()
        route.playback_command.assert_not_called()
        popen.assert_not_called()
        self.assertIsNone(speaker._temp_dir)

    def test_stale_cancellation_token_prevents_print_output(self):
        with Speaker('print') as speaker:
            token = speaker.cancellation_token()
            speaker.cancel()
            with mock.patch('builtins.print') as printed:
                result = speaker.speak('stale print dispatch', cancellation_token=token)
            self.assertFalse(result.ok)
            self.assertFalse(any(str(call.args[0]).startswith('[SPEAK]') for call in printed.call_args_list))

    @mock.patch('live.audio.subprocess.Popen')
    def test_current_cancellation_token_still_allows_speech(self, popen):
        popen.return_value = process()
        route = mock.Mock(); route.playback_command.return_value = ['player']
        speaker = self.speaker(route)
        speaker.cancel()
        self.assertTrue(speaker.speak('new dispatch', cancellation_token=speaker.cancellation_token()).ok)
        popen.assert_called_once()

    def test_real_subprocess_timeout_is_reaped_and_wave_deleted(self):
        route = mock.Mock()
        route.playback_command.return_value = [sys.executable, '-c', 'import time; time.sleep(10)']
        speaker = self.speaker(route)
        self.assertFalse(speaker.speak('real timeout').ok)
        self.assertIsNone(speaker._proc)
        self.assertFalse(speaker._tmp_wav.exists())

    @mock.patch('live.audio.subprocess.Popen')
    def test_routed_espeak_renders_wave_before_targeted_playback(self, popen):
        popen.side_effect = [process(), process()]
        route = mock.Mock(); route.playback_command.return_value = ['selected-player', '--device', SINK]
        with Speaker('espeak', route=route) as speaker:
            with mock.patch('live.audio.shutil.which', return_value='/bin/espeak-ng'):
                self.assertTrue(speaker.speak('routed speech').ok)
            commands = [call.args[0] for call in popen.call_args_list]
            self.assertEqual(commands[0][:2], ['espeak-ng', '-w'])
            self.assertEqual(commands[1], ['selected-player', '--device', SINK])
            self.assertFalse(speaker._tmp_wav.exists())


class GreetingTests(unittest.TestCase):
    def test_debounced_transition_duplicate_events_and_disconnect_bounce(self):
        gate = GreetingGate(1)
        self.assertFalse(gate.update(True, 0))
        self.assertTrue(gate.update(True, 1))
        self.assertFalse(gate.update(True, 2))
        self.assertFalse(gate.update(False, 3))
        self.assertFalse(gate.update(True, 3.5))
        self.assertFalse(gate.update(True, 5))
        self.assertFalse(gate.update(False, 6))
        self.assertFalse(gate.update(False, 7))
        self.assertEqual(gate.heart, {'ready': False, 'color': 'red'})
        self.assertFalse(gate.update(True, 8))
        self.assertTrue(gate.update(True, 9))
        self.assertEqual(gate.heart, {'ready': True, 'color': 'pink'})

    def test_exact_greeting_led_adapter_and_browser_fallback(self):
        speaker, led = mock.Mock(), mock.Mock()
        controller = GreetingController(speaker, GreetingGate(0), led)
        controller.update(True, 0); controller.update(True, 1)
        speaker.speak.assert_called_once_with('lets rock and roll', 'BLUETOOTH_READY')
        led.set_ready.assert_called_once_with(True)
        led.set_ready.side_effect = RuntimeError('LED unavailable')
        controller.update(False, 2)
        self.assertFalse(controller.heart['ready'])
        self.assertEqual(controller.led_error, 'LED unavailable')
        speaker.cancel.assert_called_once()

    def test_mockable_clock(self):
        clock = mock.Mock(side_effect=[0, 1])
        gate = GreetingGate(1, clock)
        self.assertFalse(gate.update(True)); self.assertTrue(gate.update(True))


class CliTests(unittest.TestCase):
    def test_doctor_is_read_only_and_machine_readable(self):
        with mock.patch('live.audio_check.BluetoothRoute') as route, mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            route.return_value.doctor.return_value = {'selected': {'audio_ready': False}}
            self.assertEqual(main(['doctor', '--address', ADDRESS]), 1)
            self.assertFalse(json.loads(out.getvalue())['selected']['audio_ready'])
            route.return_value.action.assert_not_called()

    def test_explicit_action(self):
        with mock.patch('live.audio_check.BluetoothRoute') as route, mock.patch('sys.stdout', new_callable=io.StringIO):
            route.return_value.action.return_value = 'ok'
            self.assertEqual(main(['connect', '--address', ADDRESS]), 0)
            route.return_value.action.assert_called_once_with('connect')


if __name__ == '__main__':
    unittest.main()
