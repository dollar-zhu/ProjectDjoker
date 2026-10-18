import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path
import numpy as np
import cv2
from live.pipeline import load_config, build
from live.runner import run
from live import check

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / 'config/dev.json'
HAVE_MODEL = (ROOT / 'models/rtmpose-m-body7-256x192/end2end.onnx').exists()

class Config(unittest.TestCase):
    def test_relative_paths_resolve_against_config_folder(self):
        cfg = load_config(DEV)
        self.assertEqual(Path(cfg['reference']['table']), ROOT / 'reference/projected2d/board_reference.json')
        self.assertEqual(Path(cfg['pose']['cache']), ROOT / 'models')

    def test_overrides_ignore_none(self):
        cfg = load_config(DEV, {'audio': {'backend': None}, 'analysis': {'serve_type': '1'}})
        self.assertEqual(cfg['audio']['backend'], 'print'); self.assertEqual(cfg['analysis']['serve_type'], '1')

    def test_board_runtime_imports_no_heavy_packages(self):
        import subprocess
        code = ('import sys, live.runner, live.check, coaching.phraser; '
                'print([m for m in ("pandas","matplotlib","torch","pyarrow") if m in sys.modules])')
        out = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(out, '[]')

@unittest.skipUnless(HAVE_MODEL, 'RTMPose model not cached')
class Pipeline(unittest.TestCase):
    def test_saved_video_runs_through_built_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / 'blank.mp4'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 30, (320, 240))
            for _ in range(10): writer.write(np.full((240, 320, 3), 80, np.uint8))
            writer.release()
            cfg = load_config(DEV, {'source': {'spec': str(video)}, 'session': {'out_dir': tmp}})
            summary = run(build(cfg))
            self.assertEqual(summary['frames'], 10)
            self.assertEqual(summary['shots'][0]['rule_id'], 'retry_capture')  # too few frames -> retry, never a guess
            self.assertTrue((Path(summary['session_dir']) / 'config.json').exists())

    def test_long_clip_warns_one_serve_per_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / 'long.mp4'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 10, (160, 120))
            for _ in range(60): writer.write(np.full((120, 160, 3), 80, np.uint8))  # 6 s > 4 s window
            writer.release()
            summary = run(build(load_config(DEV, {'source': {'spec': str(video)}, 'session': {'out_dir': tmp}})))
            self.assertEqual(len(summary['shots']), 1)
            events = [json.loads(l) for l in (Path(summary['session_dir']) / 'health.jsonl').read_text().splitlines()]
            self.assertTrue(any(e.get('event') == 'clip_longer_than_window' for e in events))

    @unittest.skipUnless((ROOT / 'local/golden/expected_pose.json').exists(), 'private golden fixtures not present')
    def test_golden_checks_pass_on_this_host(self):
        cfg = load_config(DEV)
        for fn in (lambda: check.check_assets(cfg), lambda: check.check_golden_pose(cfg, runs=2),
                   lambda: check.check_golden_decisions(cfg)):
            status, note, _ = fn()
            self.assertEqual(status, check.PASS, note)

    def test_missing_golden_is_warned_not_failed(self):
        cfg = load_config(DEV, {'check': {'golden_dir': '/nonexistent'}})
        with unittest.mock.patch.dict('os.environ', {check.GOLDEN_ENV: ''}):
            with self.assertRaises(check.GoldenMissing): check.golden(cfg, 'expected_pose.json')

    @unittest.skipUnless((ROOT / 'local/golden/expected_pose.json').exists(), 'private golden fixtures not present')
    def test_qwen_unreachable_falls_back(self):
        cfg = load_config(DEV, {'phraser': {'backend': 'qwen', 'url': 'http://127.0.0.1:9/v1/chat/completions', 'timeout_s': 0.5}})
        status, note, detail = check.check_qwen(cfg)
        self.assertEqual(status, check.WARN); self.assertEqual(detail['source'], 'canonical_fallback')

if __name__ == '__main__':
    unittest.main()
