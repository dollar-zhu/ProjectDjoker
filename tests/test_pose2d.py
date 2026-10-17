import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
import cv2
from dms.contract import load_packet
from pose2d.rtmpose import RTMPose, decode_simcc

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'models' / 'rtmpose-m-body7-256x192'
HAVE_MODEL = (MODEL / 'end2end.onnx').exists()

class Geometry(RTMPose):
    """Crop math only; no ONNX session."""
    def __init__(self):
        self.padding = 1.25; self.input_wh = (192, 256)

class CropInversion(unittest.TestCase):
    def test_aspect_fix_expands_shorter_side(self):
        g = Geometry()
        center, size = g.crop_transform([450, 350, 1300, 1560])
        np.testing.assert_allclose(center, [875, 955]); np.testing.assert_allclose(size, [1512.5 * 192 / 256, 1512.5])
        center, size = g.crop_transform([0, 0, 400, 100])  # wide box: height grows
        np.testing.assert_allclose(size, [500, 500 * 256 / 192])

    def test_decode_round_trips_original_pixels(self):
        g = Geometry(); center, size = g.crop_transform([450, 350, 1300, 1560])
        k = 192 / size[0]; points = np.array([[600.0, 500.0], [875.0, 955.0], [1200.0, 1500.0]])
        model_xy = (points - center) * k + np.array([96, 128])
        bins = np.round(model_xy * 2).astype(int)
        sx = np.zeros((3, 384)); sy = np.zeros((3, 512))
        sx[np.arange(3), bins[:, 0]] = 0.9; sy[np.arange(3), bins[:, 1]] = 0.7
        kp, score = decode_simcc(sx, sy, 2.0, center, size, (192, 256))
        np.testing.assert_allclose(kp, points, atol=0.5 / k / 2 + 1e-9)  # within half a SimCC bin
        np.testing.assert_allclose(score, 0.8)

@unittest.skipUnless(HAVE_MODEL, 'RTMPose model not cached; run pose2d.video once to download')
class ModelRun(unittest.TestCase):
    def test_pipeline_options_and_determinism(self):
        model = RTMPose(MODEL)
        self.assertTrue(model.to_rgb); self.assertEqual(model.input_wh, (192, 256)); self.assertEqual(model.split_ratio, 2.0)
        image = np.random.default_rng(0).integers(0, 255, (480, 360, 3), dtype=np.uint8)
        a = model.estimate(image, [40, 40, 320, 440]); b = model.estimate(image, [40, 40, 320, 440])
        self.assertEqual(a[0].shape, (17, 2)); np.testing.assert_array_equal(a[0], b[0])

    def test_video_cli_writes_valid_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); video = tmp / 'clip.mp4'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 30, (320, 480))
            for i in range(6):
                frame = np.full((480, 320, 3), 90, np.uint8); cv2.circle(frame, (160, 100 + i), 30, (200, 180, 160), -1)
                writer.write(frame)
            writer.release()
            out = tmp / 'run'
            subprocess.run([sys.executable, '-m', 'pose2d.video', str(video), '--crop', '40,20,280,460', '--out', str(out),
                            '--shot-id', 'synthetic', '--model-cache', str(MODEL.parent)], cwd=ROOT, check=True, capture_output=True)
            meta, arrays = load_packet(out / 'dms' / 'synthetic.json')
            self.assertEqual(arrays['pose'].shape, (6, 17, 2)); self.assertEqual(meta['features']['representation'], 'projected_2d')
            self.assertEqual(meta['timestamps']['status'], 'observed'); self.assertIsNone(meta['source']['fps'])
            self.assertTrue(np.all(np.diff(arrays['timestamps']) > 0))
            report = json.loads((out / 'run.json').read_text())
            self.assertEqual(report['video']['frames'], 6); self.assertEqual(report['model_info']['onnx_sha256'][:8], '5c0a4bf6')

if __name__ == '__main__':
    unittest.main()
