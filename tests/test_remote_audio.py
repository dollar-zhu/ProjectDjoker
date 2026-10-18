import threading
import unittest
from unittest.mock import Mock

from live.audio import AudioResult


class RemoteAudioTests(unittest.TestCase):
    def service(self):
        from live.remote_audio import AudioService
        speaker = Mock()
        speaker.cancellation_token.return_value = 7
        speaker.speak.side_effect = lambda text, **kw: AudioResult(True, 'piper', text, 0)
        route = Mock()
        route.address = '44:DB:D2:05:75:5E'
        route.status.return_value = dict(address=route.address, paired=True, connected=True, audio_ready=True)
        return AudioService(speaker, route), speaker

    def test_conversation_selects_configured_board_route(self):
        from live.conversation import LiveConversation
        from live.remote_audio import RemoteRoute
        controller = LiveConversation('remote-test', config={'audio': {
            'remote_url': 'http://127.0.0.1:18877', 'bluetooth_address': '44:DB:D2:05:75:5E'}})
        try:
            self.assertIsInstance(controller._selected_route(), RemoteRoute)
        finally:
            controller.close()

    def test_cancel_before_request_arrives_never_speaks(self):
        service, speaker = self.service()
        service.cancel('delayed')
        result = service.speak('delayed', 'Do not play this')
        self.assertFalse(result['ok'])
        speaker.speak.assert_not_called()

    def test_cancel_during_speech_and_reject_overlapping_requests(self):
        service, speaker = self.service()
        started, release = threading.Event(), threading.Event()
        def speak(text, **kw):
            started.set(); release.wait(2)
            return AudioResult(False, 'piper', text, 0, 'cancelled')
        speaker.speak.side_effect = speak
        speaker.cancel.side_effect = release.set
        thread = threading.Thread(target=service.speak, args=('first', 'Hello'))
        thread.start()
        try:
            self.assertTrue(started.wait(1))
            self.assertFalse(service.speak('second', 'Overlap')['ok'])
            service.cancel('first')
            thread.join(1)
            self.assertFalse(thread.is_alive())
            speaker.cancel.assert_called_once()
        finally:
            release.set(); thread.join()

    def test_http_roundtrip_and_selected_address_validation(self):
        from live.remote_audio import RemoteRoute, RemoteSpeaker, make_server
        service, speaker = self.service()
        server = make_server(service, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        url = f'http://127.0.0.1:{server.server_port}'
        try:
            route = RemoteRoute(url, service.route.address)
            self.assertTrue(route.status()['audio_ready'])
            wrong = RemoteRoute(url, '00:11:22:33:44:55')
            self.assertFalse(wrong.status()['audio_ready'])
            client = RemoteSpeaker(route)
            self.assertTrue(client.speak('Hello from the app').ok)
            self.assertEqual(speaker.speak.call_args.args, ('Hello from the app',))
            token = client.cancellation_token(); client.cancel()
            self.assertFalse(client.speak('Stale', cancellation_token=token).ok)
            self.assertEqual(speaker.speak.call_count, 1)
            client.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_remote_endpoint_must_be_loopback(self):
        from live.remote_audio import RemoteRoute
        for url in ('https://example.com', 'http://192.168.1.1:18877', 'file:///tmp/audio'):
            with self.assertRaises(ValueError): RemoteRoute(url, '44:DB:D2:05:75:5E')
