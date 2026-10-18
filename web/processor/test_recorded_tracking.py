import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import worker


FIXTURE = Path(__file__).parent/'fixtures/live-serve-168.json'


class RecordedTrackingTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text())
        self.job = {'options': self.data['options'], 'meta': self.data['meta'],
                    'capture': {'source': 'Ventuno USB webcam',
                                'tracking_backend': 'Host CPU · ONNX Runtime',
                                'tracking_options': copy.deepcopy(self.data['options']),
                                'tracking_image_size': [640, 480],
                                'crop_mode': 'recorded_tracking_extent'}}

    def test_original_live_observations_retain_finish_without_second_inference(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d/'job.json').write_text(json.dumps(self.job))
            (d/'tracking.json').write_text(json.dumps(self.data['frames']))
            with patch.object(worker, 'command', side_effect=AssertionError('Live poses must not be re-inferred')):
                worker.process(d)
                worker.process(d)  # Refreshing a saved review replaces its generated DMS packet.
            result = json.loads((d/'result.json').read_text())
            self.assertEqual([s['status'] for s in result['stages']], ['estimated']*6)
            self.assertEqual(result['stages'][-1]['end'], 2.8069)
            self.assertEqual(result['frames'], [{k: f[k] for k in ('time', 'xy', 'scores')} for f in self.data['frames']])
            self.assertEqual(result['stats']['pose_source'], 'recorded_live_tracking')
            self.assertEqual(result['stats']['backend'], self.job['capture']['tracking_backend'])
            packet = json.loads(next((d/'dms').glob('*.json')).read_text())
            self.assertEqual(packet['source']['runtime'], self.job['capture']['tracking_backend'])
            self.assertEqual(json.loads((d/'job.json').read_text())['status'], 'complete')

    def test_completion_label_cannot_replace_missing_arm_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            self.job['capture']['completion'] = 'observed_reach_descent_recovery'
            for f in self.data['frames']:
                if f['time'] > 2.4:
                    f['scores'][8] = f['scores'][10] = .1
            (d/'job.json').write_text(json.dumps(self.job))
            (d/'tracking.json').write_text(json.dumps(self.data['frames']))
            worker.process(d)
            result = json.loads((d/'result.json').read_text())
            self.assertEqual(result['stages'][-1]['status'], 'unavailable')

    def test_changed_selection_or_invalid_trace_requires_fresh_inference(self):
        self.assertTrue(hasattr(worker, 'recorded_tracking'), 'Need validated reuse of recorded observations')
        for variant in ['crop', 'view', 'size', 'no_provenance', 'timestamps', 'outside_video', 'shape', 'nonfinite']:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as td:
                job = copy.deepcopy(self.job)
                frames = copy.deepcopy(self.data['frames'])
                if variant == 'crop': job['options']['crop'] = [0, 0, 1, 1]
                if variant == 'view': job['options']['view'] = 'side'
                if variant == 'size': job['meta']['width'] = 1280
                if variant == 'no_provenance': del job['capture']['tracking_options']
                if variant == 'timestamps': frames[1]['time'] = frames[0]['time']
                if variant == 'outside_video': frames[-1]['time'] = 100
                if variant == 'shape': frames[0]['xy'] = [[1, 2]]
                if variant == 'nonfinite': frames[0]['scores'][0] = float('nan')
                d = Path(td)
                (d/'tracking.json').write_text(json.dumps(frames))
                self.assertIsNone(worker.recorded_tracking(d, job))


if __name__ == '__main__': unittest.main()
