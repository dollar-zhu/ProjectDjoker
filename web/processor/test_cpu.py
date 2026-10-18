import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

import worker


class CpuTests(unittest.TestCase):
    def test_offline_board_falls_back_to_local_model(self):
        model = Path(os.environ.get('DJOKER_ONNX', Path(__file__).resolve().parents[2] / 'demo/ventuno-pose/et/onnx/rtmpose_body2d.onnx'))
        if not model.exists():
            self.skipTest('Local wholebody ONNX model is not installed')
        with tempfile.TemporaryDirectory() as base:
            d = Path(base) / str(uuid.uuid4()); d.mkdir()
            worker.command(['ffmpeg','-v','error','-f','lavfi','-i','color=c=green:s=320x240:d=0.5','-c:v','libx264',str(d/'video.mp4')])
            (d/'job.json').write_text(json.dumps({'id': d.name, 'options': {'crop':[0,0,1,1], 'view':'rear', 'handedness':'right'}, 'meta':{'width':320,'height':240}}))
            real = worker.command
            def offline(args, timeout=120):
                if args[0] == 'adb':
                    raise RuntimeError('device unavailable')
                return real(args, timeout)
            with patch.object(worker, 'command', side_effect=offline):
                worker.process(d)
            result = json.loads((d/'result.json').read_text())
            self.assertEqual(json.loads((d/'job.json').read_text())['status'], 'complete')
            self.assertIn('CPU', result['stats']['backend'])
            self.assertEqual(len(result['frames']), 10)
            self.assertEqual(result['feedback']['mode'], 'retry')
            self.assertEqual(result['events'], [])


if __name__ == '__main__': unittest.main()
