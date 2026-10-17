"""Video -> RTMPose 2D skeleton -> DMS v0.1 packet, with native output and overlays kept for review.

Development-host tool. Uses a fixed operator crop (no detector) and observed container timestamps.
"""
import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
import numpy as np
import cv2
from dms.contract import export_canonical, interior_angles
from dms.definitions import JOINT_NAMES
from .rtmpose import RTMPose, fetch_model, sha256, COCO17_EVIDENCE

ROOT = Path(__file__).resolve().parents[1]
EDGES = [(5,7),(7,9),(6,8),(8,10),(5,6),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16),(0,1),(0,2),(1,3),(2,4)]
LEFT, RIGHT, MID = (255,140,30), (30,140,255), (220,220,220)  # BGR: player's left blue, right orange

def read_video(path):
    cap = cv2.VideoCapture(str(path)); frames, times = [], []
    if not cap.isOpened(): raise RuntimeError(f'Cannot open {path}')
    while True:
        ok, frame = cap.read()
        if not ok: break
        frames.append(frame); times.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000)
    cap.release(); times = np.asarray(times)
    if not frames: raise RuntimeError('No frames decoded')
    if not np.all(np.diff(times) > 0): raise RuntimeError('Decoded timestamps are not strictly increasing')
    return frames, times - times[0]

def color(a, b=None):
    side = lambda j: 'l' if JOINT_NAMES[j].startswith('left') else 'r' if JOINT_NAMES[j].startswith('right') else 'm'
    s = {side(a)} if b is None else {side(a), side(b)}
    return LEFT if s == {'l'} else RIGHT if s == {'r'} else MID

def draw(frame, kp, score, box, threshold, label):
    img = frame.copy(); x1, y1, x2, y2 = map(int, box)
    cv2.rectangle(img, (x1, y1), (x2, y2), (0,255,255), 2)
    for a, b in EDGES:
        if np.isfinite(kp[[a,b]]).all() and min(score[a], score[b]) >= threshold:
            cv2.line(img, tuple(np.int32(kp[a])), tuple(np.int32(kp[b])), color(a, b), 5, cv2.LINE_AA)
    for j in range(17):
        if not np.isfinite(kp[j]).all(): continue
        p = tuple(np.int32(kp[j]))
        cv2.circle(img, p, 9, color(j), -1 if score[j] >= threshold else 2, cv2.LINE_AA)
    cv2.putText(img, label, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255,255,255), 4, cv2.LINE_AA)
    cv2.putText(img, label, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0,0,0), 2, cv2.LINE_AA)
    return img

def contact_sheet(images, columns=4, width=400):
    tiles = [cv2.resize(i, (width, int(i.shape[0] * width / i.shape[1]))) for i in images]
    while len(tiles) % columns: tiles.append(np.zeros_like(tiles[0]))
    return np.vstack([np.hstack(tiles[r:r + columns]) for r in range(0, len(tiles), columns)])

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', type=Path)
    p.add_argument('--crop', required=True, help='Fixed player crop x1,y1,x2,y2 in original pixels')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--shot-id', required=True)
    p.add_argument('--player', default='unknown_player')
    p.add_argument('--handedness', choices=['left','right','unknown'], default='unknown')
    p.add_argument('--camera-view', default='unknown')
    p.add_argument('--model', default='rtmpose-m-body7-256x192')
    p.add_argument('--model-cache', type=Path, default=ROOT / 'models')
    p.add_argument('--provider', default='CPUExecutionProvider')
    p.add_argument('--draw-threshold', type=float, default=0.3, help='Overlay only; does not alter data')
    p.add_argument('--gap-ms', type=float, default=200.0)
    a = p.parse_args()
    box = [float(v) for v in a.crop.split(',')]
    if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]: p.error('--crop must be x1,y1,x2,y2')
    if a.out.exists() and any(a.out.iterdir()): p.error(f'{a.out} must be new or empty')

    frames, times = read_video(a.video); h, w = frames[0].shape[:2]
    model = RTMPose(fetch_model(a.model, a.model_cache), providers=[a.provider])
    kps, raw, ms = [], [], []
    for frame in frames:
        t0 = time.perf_counter(); k, s = model.estimate(frame, box); ms.append((time.perf_counter() - t0) * 1000)
        kps.append(k); raw.append(s)
    kps, raw = np.array(kps), np.array(raw)

    # Missing, never guessed: non-positive SimCC peak or a location outside the image.
    outside = (kps[..., 0] < 0) | (kps[..., 0] > w - 1) | (kps[..., 1] < 0) | (kps[..., 1] > h - 1)
    missing = (raw <= 0) | outside
    pose = kps.copy(); pose[missing] = np.nan
    confidence = np.clip(raw, 0, 1); confidence[missing] = np.nan
    center, size = model.crop_transform(box)
    a.out.mkdir(parents=True, exist_ok=True)
    np.savez(a.out / 'rtmpose_native.npz', keypoints_xy=kps, scores_raw=raw, timestamps_s=times,
             frame_index=np.arange(len(frames)), crop_xyxy=np.array(box), model_crop_center=center, model_crop_size=size)

    source = {'model': a.model, 'coordinate_system': 'image_2d', 'camera_view': a.camera_view, 'fps': None,
              'axis_convention': 'x_right_y_down', 'units': 'pixels', 'metric_space': True, 'image_size': [w, h],
              'comparison_profile_id': None, 'runtime': model.info['runtime'], 'runtime_provider': model.info['providers_active'][0],
              'onnx_sha256': model.info['onnx_sha256'], 'crop_xyxy': box, 'crop_mode': 'fixed_operator',
              'video_sha256': sha256(a.video)}
    packet = export_canonical(a.out / 'dms', shot_id=a.shot_id, player=a.player, handedness=a.handedness, source=source,
        pose=pose, timestamps=times, joint_confidence=confidence, confidence_kind='tracking_score',
        score_definition='rtmpose-simcc-mean-xy-peak-raw-clipped-0-1', mapping_evidence=COCO17_EVIDENCE,
        events={'max_knee_flexion': None, 'contact': None})

    gaps = np.diff(times) * 1000
    knee = [11,13,15,12,14,16]
    report = {
        'video': {'path': str(a.video), 'sha256': source['video_sha256'], 'width': w, 'height': h, 'frames': len(frames),
                  'duration_s': float(times[-1]), 'median_interval_ms': float(np.median(gaps)),
                  'gaps_over_threshold': [{'after_frame': int(i), 'ms': float(gaps[i])} for i in np.flatnonzero(gaps > a.gap_ms)],
                  'max_gap_ms': float(gaps.max()), 'fps': None, 'fps_note': 'variable frame rate; observed timestamps used'},
        'model': a.model, 'model_info': model.info, 'mapping': {'native': 'COCO-17 (RTMPose body7)', 'canonical17_evidence': COCO17_EVIDENCE},
        'crop': {'operator_xyxy': box, 'model_input_center': center.tolist(), 'model_input_size': size.tolist()},
        'timing_ms': {'per_frame_median': float(np.median(ms)), 'per_frame_p95': float(np.percentile(ms, 95)), 'note': 'crop+inference+decode on development host'},
        'scores': {'raw_min': float(raw.min()), 'raw_max': float(raw.max()), 'fraction_raw_above_1': float((raw > 1).mean()),
                   'per_joint_median_raw': {n: float(v) for n, v in zip(JOINT_NAMES, np.median(raw, 0))},
                   'missing_joint_samples': int(missing.sum()), 'outside_image_samples': int(outside.sum())},
        'quality_flags': {'frames_all_knee_joints_conf_ge_0.8': int((confidence[:, knee] >= 0.8).all(1).sum()), 'frames_total': len(frames)},
        'dms_packet': str(packet.relative_to(a.out)),
        'limitations': ['Development-host run, not board inference', 'Fixed operator crop; no person detection',
                        'Scores are raw SimCC peaks clipped to [0,1], not calibrated probabilities',
                        'Mapping is the documented COCO-17 order; left/right should be checked visually on the overlay'],
    }
    (a.out / 'run.json').write_text(json.dumps(report, indent=2) + '\n')

    angles = interior_angles(pose)
    rendered = [draw(f, k, s, box, a.draw_threshold,
                     f'#{i} t={t*1000:.0f}ms  Lknee {angles[i,2]:.0f}  Rknee {angles[i,3]:.0f}  Relb {angles[i,1]:.0f}')
                for i, (f, k, s, t) in enumerate(zip(frames, kps, raw, times))]
    picks = np.linspace(0, len(frames) - 1, 12).round().astype(int)
    cv2.imwrite(str(a.out / 'contact_sheet.jpg'), contact_sheet([rendered[i] for i in picks]))
    if shutil.which('ffmpeg'):
        frame_dir = a.out / '_frames'; frame_dir.mkdir()
        lines = []
        for i, img in enumerate(rendered):
            cv2.imwrite(str(frame_dir / f'{i:05d}.jpg'), cv2.resize(img, (w // 2 * 2 // 2, h // 2 * 2 // 2)))
            lines += [f"file '{i:05d}.jpg'", f'duration {(times[i+1]-times[i]) if i + 1 < len(times) else gaps.mean()/1000:.6f}']
        (frame_dir / 'list.txt').write_text('\n'.join(lines) + '\n')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-i', 'list.txt', '-vsync', 'vfr', '-pix_fmt', 'yuv420p',
                        '-c:v', 'libx264', '../overlay.mp4'], cwd=frame_dir, check=True)
        shutil.rmtree(frame_dir)
    print(json.dumps({'packet': str(packet), 'frames': len(frames), 'median_ms': report['timing_ms']['per_frame_median'],
                      'raw_score_range': [report['scores']['raw_min'], report['scores']['raw_max']]}))

if __name__ == '__main__':
    main()
