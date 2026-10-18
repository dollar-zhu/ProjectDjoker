import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

from live.led import BrowserLED, RouterLED, make_led

ROOT = Path(__file__).resolve().parents[1]


class AudioIPC(unittest.TestCase):
    def test_commands_are_session_scoped_and_recordings_removed(self):
        controller = Mock()
        controller.snapshot.return_value = {'state': 'IDLE', 'enabled': False}
        module = types.ModuleType('live.conversation')
        module.LiveConversation = Mock()
        module.LiveConversation.from_environment.return_value = controller
        spec = importlib.util.spec_from_file_location('audio_bridge_test', ROOT / 'web/processor/audio_bridge.py')
        bridge_module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'live.conversation': module}):
            spec.loader.exec_module(bridge_module)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            bridge = bridge_module.AudioBridge(directory)
            try:
                def wait_for(predicate):
                    deadline = time.monotonic() + 2
                    while not predicate() and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertTrue(predicate())

                wait_for(lambda: (directory / 'audio-status.json').exists())
                (directory / 'audio-command.json').write_text(json.dumps({'action': 'enable', 'session_id': 'old'}))
                wait_for(lambda: not (directory / 'audio-command.json').exists())
                controller.command.assert_not_called()
                command = {'action': 'cancel', 'session_id': bridge.session_id}
                (directory / 'audio-command.json').write_text(json.dumps(command))
                wait_for(lambda: controller.command.called)
                controller.command.assert_called_once_with(command)
                def upload(session, length, data=b''):
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.settimeout(2)
                        client.connect(str(directory / 'audio.sock'))
                        client.sendall(json.dumps({'session_id': session, 'length': length}).encode() + b'\n' + data)
                        return json.loads(client.recv(1024))

                self.assertIn('error', upload('old', 44))
                self.assertIn('error', upload(bridge.session_id, 320045))
                controller.submit_wav.assert_not_called()
                controller.submit_wav.return_value = True
                self.assertTrue(upload(bridge.session_id, 44, b'x' * 44)['accepted'])
                controller.submit_wav.assert_called_once_with(b'x' * 44)
                self.assertFalse((directory / 'utterance.wav').exists())
            finally:
                bridge.close()
            controller.close.assert_called_once()
            self.assertFalse((directory / 'utterance.wav').exists())
            self.assertFalse((directory / 'audio-status.json').exists())

    def test_local_camera_reuses_existing_latest_frame_reader(self):
        stubs = {}
        for module_name, names in {
            'capture': ['ServeCapture', 'ReadyServeCapture', 'ManualCapture', 'PlayerCrop', 'pose_signal', 'ready_pose'],
            'pose': ['crop_input', 'decode'],
            'worker': ['ONNX', 'prepare', 'process', 'update'],
            'audio_bridge': ['AudioBridge'],
        }.items():
            module = types.ModuleType(module_name)
            for name in names:
                setattr(module, name, Mock())
            stubs[module_name] = module
        spec = importlib.util.spec_from_file_location('live_capture_audio_test', ROOT / 'web/processor/live_capture.py')
        module = importlib.util.module_from_spec(spec)
        original_path = list(sys.path)
        try:
            with patch.dict(sys.modules, stubs):
                spec.loader.exec_module(module)
            with patch.object(module.subprocess, 'Popen') as spawn, patch.object(module.threading, 'Thread'), \
                    patch.dict('os.environ', {'DJOKER_CAMERA_SOURCE': 'local',
                                              'DJOKER_CAMERA_DEVICE': '/dev/v4l/by-id/selected-camera'}):
                camera = module.BoardCamera(Mock())
                argv = spawn.call_args.args[0]
                self.assertEqual(argv[0], 'ffmpeg')
                self.assertIn('/dev/v4l/by-id/selected-camera', argv)
                self.assertNotIn('adb', argv)
                camera.close()
        finally:
            sys.path[:] = original_path


class LEDCapabilities(unittest.TestCase):
    def test_default_is_explicit_browser_fallback(self):
        led = make_led()
        self.assertIsInstance(led, BrowserLED)
        self.assertIn('blue monochrome', led.capability)
        led.set_ready(True)
        self.assertIsNone(led.error)

    def test_missing_router_is_actionable_and_not_fatal(self):
        led = RouterLED('/nonexistent/djoker-router.sock')
        led.set_ready(True)
        self.assertIn('LED unavailable', led.error)

    def test_rpc_is_bounded_and_uses_safe_named_callback(self):
        msgpack = types.ModuleType('msgpack')
        msgpack.packb = Mock(return_value=b'packed')
        msgpack.Unpacker = Mock()
        msgpack.Unpacker.return_value.__iter__ = lambda self: iter([[1, 1, None, None]])
        with patch.dict(sys.modules, {'msgpack': msgpack}), patch('live.led.socket.socket') as socket:
            client = socket.return_value.__enter__.return_value
            client.recv.return_value = b'reply'
            led = RouterLED()
            led.set_ready(True)
            msgpack.packb.assert_called_once_with([0, 1, 'djoker_audio_ready', [True]])
            self.assertTrue(client.settimeout.called)
            self.assertIsNone(led.error)


if __name__ == '__main__':
    unittest.main()
