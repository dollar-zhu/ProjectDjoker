"""Create private golden fixtures for djoker-check from one of your own serve clips (default: local/golden/, git-ignored).

Writes a lossless crop of one frame + the expected RTMPose skeleton from this host, the clip's DMS packet,
and the expected strict/demo decisions and score. The board then proves it reproduces them.

    .venv/bin/python scripts/make_golden.py --video serve.mov --crop 450,350,1300,1560 --frame 56
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from pose2d.rtmpose import RTMPose, fetch_model, sha256  # noqa: E402
from pose2d.video import read_video  # noqa: E402
from coaching.board_feedback import decide  # noqa: E402

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--video', type=Path, required=True)
    p.add_argument('--crop', required=True, help='Player crop x1,y1,x2,y2 used for the pose packet and the fixture')
    p.add_argument('--frame', type=int, help='Frame for the pose fixture (default: deepest knee bend)')
    p.add_argument('--handedness', default='right'); p.add_argument('--out', type=Path, default=ROOT / 'local/golden')
    a = p.parse_args()
    box = [float(v) for v in a.crop.split(',')]
    a.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:  # DMS packet via the normal video CLI
        import subprocess
        subprocess.run([sys.executable, '-m', 'pose2d.video', str(a.video), '--crop', a.crop, '--out', tmp, '--shot-id', 'golden',
                        '--handedness', a.handedness, '--model-cache', str(ROOT / 'models')], cwd=ROOT, check=True, capture_output=True)
        shutil.rmtree(a.out / 'dms', ignore_errors=True); shutil.copytree(Path(tmp) / 'dms', a.out / 'dms')
    packet = a.out / 'dms/golden.json'
    rules, table = ROOT / 'coaching/rules.json', ROOT / 'reference/projected2d/board_reference.json'
    strict, demo = decide(packet, table, rules), decide(packet, table, rules, allow_unvalidated_reference=True)
    frame_index = a.frame
    if frame_index is None:
        from compare2d.serve2d import serve_metrics
        arrays = {k: np.load(a.out / f'dms/golden_{k}.npy') for k in ('pose', 'timestamps')}
        frame_index = serve_metrics(arrays['timestamps'], arrays['pose'])['load_frame']
    frames, _ = read_video(a.video); h, w = frames[0].shape[:2]
    x0, y0 = max(0, int(box[0] - 150)), max(0, int(box[1] - 150)); x1, y1 = min(w, int(box[2] + 150)), min(h, int(box[3] + 150))
    cv2.imwrite(str(a.out / 'frame.png'), frames[frame_index][y0:y1, x0:x1], [cv2.IMWRITE_PNG_COMPRESSION, 9])
    image = cv2.imread(str(a.out / 'frame.png')); fixture_box = [box[0] - x0, box[1] - y0, box[2] - x0, box[3] - y0]
    model = RTMPose(fetch_model('rtmpose-m-body7-256x192', ROOT / 'models')); kp, sc = model.estimate(image, fixture_box)
    (a.out / 'expected_pose.json').write_text(json.dumps({
        'image': 'frame.png', 'image_sha256': sha256(a.out / 'frame.png'), 'box_xyxy': fixture_box,
        'model_onnx_sha256': model.info['onnx_sha256'], 'keypoints_xy': np.round(kp, 3).tolist(), 'scores': np.round(sc, 4).tolist(),
        'tolerance_px': 6.0, 'tolerance_note': 'about two SimCC bins at this crop scale; covers runtime/platform numeric drift',
        'source': f'{a.video.name} frame {frame_index}'}, indent=1) + '\n')
    (a.out / 'expected_decisions.json').write_text(json.dumps({'packet': 'dms/golden.json', 'serve_type': 'unknown', 'expected': {
        'strict': {'rule_id': strict['rule_id'], 'mode': strict['mode'], 'score': strict['rating']['score']},
        'demo': {'rule_id': demo['rule_id'], 'praise_rule_id': demo['praise_rule_id'], 'score': demo['rating']['score']}}}, indent=1) + '\n')
    print(json.dumps({'out': str(a.out), 'frame': frame_index, 'strict': strict['rule_id'], 'demo': demo['rule_id'],
                      'demo_score': demo['rating']['score']}, indent=1))

if __name__ == '__main__':
    main()
