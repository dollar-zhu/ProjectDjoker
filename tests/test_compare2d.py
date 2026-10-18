import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from dms.contract import export_canonical
from compare2d.serve2d import detect_events, estimate_yaw, hip_width_ratio
from compare2d.reference import project, unmirror, chirality, to_canonical, YAWS
from compare2d.compare import compare

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'reference/projected2d/djokovic_knee_load_2d.json'
SOURCE = ROOT / 'reference/source/data/keypoints'

def synthetic_serve(n=60, load=25, reach=40, wrist_peak=None):
    """Standing 2D figure (pixels, y down) whose knees bend most at `load` and right wrist peaks at `reach`."""
    t = np.arange(n) / 60; pose = np.full((n, 17, 2), np.nan)
    bend = 60 * np.exp(-((np.arange(n) - load) / 6.0) ** 2)  # degrees of flexion
    for i in range(n):
        for side, x in ((11, 90), (12, 110)):
            hip = np.array([x, 300.0]); th = np.radians(bend[i] / 2)
            knee = hip + 100 * np.array([np.sin(th), np.cos(th)]); ankle = knee + 100 * np.array([-np.sin(th), np.cos(th)])
            pose[i, side], pose[i, side + 2], pose[i, side + 4] = hip, knee, ankle
        pose[i, 5], pose[i, 6] = [90, 150], [110, 150]
        pose[i, 7], pose[i, 8], pose[i, 9] = [80, 220], [120, 220], [80, 290]
        peak = reach if wrist_peak is None else wrist_peak
        pose[i, 10] = [130, 150 - 120 * np.exp(-((i - peak) / 4.0) ** 2)]
    return t, pose

class Events(unittest.TestCase):
    def test_load_before_reach(self):
        t, pose = synthetic_serve()
        load, reach, angles, flags = detect_events(t, pose)
        self.assertEqual(reach, 40); self.assertLessEqual(abs(load - 25), 1); self.assertEqual(flags, [])

    def test_missing_leg_does_not_turn_two_knee_average_into_one_knee_minimum(self):
        t, pose = synthetic_serve()
        t = np.arange(len(t)) / 20
        pose[18, 15] = np.nan
        pose[18, 12], pose[18, 14], pose[18, 16] = [110,300], [210,300], [160,386]
        load, reach, _, flags = detect_events(t, pose)
        self.assertEqual(load, 25)
        self.assertEqual(reach, 40)
        self.assertEqual(flags, [])

    def test_no_complete_knee_pair_returns_unavailable(self):
        t, pose = synthetic_serve()
        pose[:,15] = np.nan
        load, _, _, flags = detect_events(t, pose)
        self.assertIsNone(load)
        self.assertIn('no_complete_knee_pair', flags)

    def test_wrist_peak_before_loading_fails_closed(self):
        t, pose = synthetic_serve(load=35, wrist_peak=15)
        load, reach, _, flags = detect_events(t, pose)
        self.assertIsNone(load); self.assertIn('deeper_knee_flexion_after_reach', flags)

class View(unittest.TestCase):
    def test_yaw_from_ratio(self):
        self.assertAlmostEqual(estimate_yaw(0.0, 0.46), 0.0); self.assertAlmostEqual(estimate_yaw(0.46, 0.46), 90.0)
        self.assertAlmostEqual(estimate_yaw(0.23, 0.46), 30.0, places=6)

    def test_projection_sign_and_profile_preserves_sagittal_angle(self):
        # Proper z-up frame: hips along +x (left hip at +x), knee bent 90 deg forward (+y facing = h x up... use cross).
        h = np.array([1.0, 0, 0]); forward = np.cross(h, [0, 0, 1])
        p = np.zeros((1, 17, 3)); p[0, 1] = [-0.1, 0, 1]; p[0, 4] = [0.1, 0, 1]
        p[0, 5] = p[0, 4] + 0.5 * forward; p[0, 6] = p[0, 5] + [0, 0, -0.5]
        c = to_canonical(p)
        two = project(c, 0.0, 0)[0]
        u, v = two[11] - two[13], two[15] - two[13]
        self.assertAlmostEqual(np.degrees(np.arccos(u @ v / np.linalg.norm(u) / np.linalg.norm(v))), 90, places=6)
        self.assertGreater(project(c, 0.0, 30)[0, 11, 0], project(c, 0.0, 30)[0, 12, 0])  # +yaw: left hip right of right hip
        self.assertLess(project(c, 0.0, -30)[0, 11, 0], project(c, 0.0, -30)[0, 12, 0])

    @unittest.skipUnless(SOURCE.exists(), 'reference source missing')
    def test_source_is_mirrored_and_unmirror_fixes_it(self):
        p = np.load(sorted(SOURCE.glob('*.npy'))[0]).astype(float)
        self.assertLess(chirality(p), 0); self.assertGreater(chirality(unmirror(p)), 0)

@unittest.skipUnless(REFERENCE.exists(), 'run python -m compare2d.reference first')
class Comparison(unittest.TestCase):
    def packet(self, tmp, pose, handedness='right', scale=400.0):
        times = np.arange(len(pose)) / 60
        pix = pose * scale + 800
        return export_canonical(Path(tmp) / 'p', shot_id='synthetic', player='test', handedness=handedness,
            source={'model': 'synthetic', 'coordinate_system': 'image_2d', 'camera_view': 'test', 'fps': None,
                    'axis_convention': 'x_right_y_down', 'units': 'pixels', 'metric_space': True},
            pose=pix, timestamps=times, joint_confidence=np.full((len(pose), 17), 0.9), confidence_kind='tracking_score',
            score_definition='synthetic', mapping_evidence='synthetic', events={})

    def reference_serve_2d(self, yaw):
        ref = json.loads(REFERENCE.read_text()); rec = ref['records'][0]
        p3 = unmirror(np.load(SOURCE / rec['filename']).astype(float)); k = rec['load_3d_frame']
        hip = p3[k, 4, :2] - p3[k, 1, :2]
        return project(to_canonical(p3), float(np.arctan2(hip[1], hip[0])), yaw), rec

    def test_projected_reference_serve_round_trips(self):
        pose, rec = self.reference_serve_2d(20)
        with tempfile.TemporaryDirectory() as tmp:
            production, diag = compare(self.packet(tmp, pose), REFERENCE)
        self.assertEqual(production['status'], 'insufficient_evidence'); self.assertIsNone(production['delta'])
        self.assertFalse(production['feedback_allowed'])
        self.assertAlmostEqual(diag['view']['estimated_yaw_deg'], 20, delta=12)
        grid = json.loads(REFERENCE.read_text())['camera_model']['yaw_grid_deg']
        expected = rec['by_yaw'][grid.index(20)]['knee_2d_at_load']
        np.testing.assert_allclose(diag['user_knee_at_load'], expected, atol=1e-6)

    def test_deterministic_and_unknown_handedness_blocks(self):
        pose, _ = self.reference_serve_2d(10)
        with tempfile.TemporaryDirectory() as tmp:
            a = compare(self.packet(tmp, pose), REFERENCE)
        with tempfile.TemporaryDirectory() as tmp:
            b = compare(self.packet(tmp, pose), REFERENCE)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        with tempfile.TemporaryDirectory() as tmp:
            production, diag = compare(self.packet(tmp, pose, handedness='unknown'), REFERENCE)
        self.assertIn('handedness_unknown_or_mismatch', production['reasons']); self.assertIsNone(production['delta'])

    def test_square_on_view_is_outside_supported_band(self):
        pose, _ = self.reference_serve_2d(80)
        with tempfile.TemporaryDirectory() as tmp:
            production, _ = compare(self.packet(tmp, pose), REFERENCE)
        self.assertIn('view_outside_supported_band', production['reasons'])

if __name__ == '__main__':
    unittest.main()
