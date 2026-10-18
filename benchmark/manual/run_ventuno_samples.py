"""Diagnostic: selected video crops -> existing Ventuno ExecuTorch RTMPose -> overlays.

Run with demo/ventuno-pose/et/.venv-et/bin/python. Manual ROIs deliberately isolate
pose inference from person detection. Source slow motion is preserved.
"""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'demo/ventuno-pose'))
import posepipe as P

MODEL = '/home/arduino/models/et/rtmpose_qnn_fp16_QCS8275.pte'
RUNNER = '/home/arduino/git/executorch/build-x86/examples/qualcomm/executor_runner/qnn_executor_runner'
ENV = 'export LD_LIBRARY_PATH=/home/arduino/git/executorch/build-x86/backends/qualcomm:/usr/lib ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib"; '
ROIS = {'p001': (.64, .68, .64), 'a001': (.65, .60, .75), 'a004': (.53, .60, .70)}


def run(args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(result.stdout)
    return result.stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--serial', default='242692658')
    ap.add_argument('--fps', type=int, default=15)
    a = ap.parse_args()
    if a.fps < 1:
        ap.error('--fps must be positive')
    base = Path(__file__).parent
    stamp = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    out = base / 'runs' / stamp
    inp = out / 'inputs'
    inp.mkdir(parents=True)
    board = '/home/arduino/djoker-bench/' + stamp
    adb = ['adb', '-s', a.serial]
    manifest = json.loads((base / 'samples/manifest.json').read_text())
    entries = []
    for clip in manifest['clips']:
        if clip['id'] not in ROIS:
            continue
        frames_dir = out / clip['id'] / 'frames'
        frames_dir.mkdir(parents=True)
        run(['ffmpeg', '-v', 'error', '-i', str(base / 'samples' / clip['file']),
             '-vf', f'fps={a.fps}', str(frames_dir / '%05d.png')])
        for j, path in enumerate(sorted(frames_dir.glob('*.png'))):
            im = cv2.imread(str(path))
            h, w = im.shape[:2]
            cx, cy, hh = ROIS[clip['id']]
            # P.rtm_matrix multiplies side by 1.3; set actual crop height to hh*h.
            roi = (cx*w, cy*h, hh*h/1.3, -np.pi/2)
            crop, matrix = P.rtm_crop(cv2.cvtColor(im, cv2.COLOR_BGR2RGB), roi)
            index = len(entries)
            P.rtm_input(crop).astype('<f4').tofile(inp / f'{index:05d}.raw')
            entries.append({'clip': clip['id'], 'index': j, 'image': str(path.relative_to(out)),
                            'source_time_s': clip['source_start_s'] + j/a.fps,
                            'matrix': matrix.tolist(), 'manual_roi': list(roi)})
    (inp / 'list.txt').write_text(''.join(f'{board}/inputs/{i:05d}.raw\n' for i in range(len(entries))))
    run(adb + ['shell', f'mkdir -p {shlex.quote(board)}/out'])
    run(adb + ['push', str(inp), board + '/'])
    command = (ENV + f'/usr/bin/time -v {RUNNER} --model_path {MODEL} '
               f'--input_list_path {board}/inputs/list.txt --output_folder_path {board}/out '
               f'--iteration 1 --warm_up 2')
    t = time.monotonic()
    log = run(adb + ['shell', command])
    wall = time.monotonic() - t
    (out / 'runner.log').write_text(log)
    run(adb + ['pull', board + '/out', str(out / 'raw_outputs')])
    latencies = [float(x) for x in re.findall(r'1 inference took ([\d.]+) ms', log)]
    rss = re.search(r'Maximum resident set size \(kbytes\): (\d+)', log)
    stats = {}
    for i, entry in enumerate(entries):
        px = np.fromfile(out / 'raw_outputs' / f'output_{i}_0.raw', '<f4').reshape(133, 384)
        py = np.fromfile(out / 'raw_outputs' / f'output_{i}_1.raw', '<f4').reshape(133, 512)
        if not (np.isfinite(px).all() and np.isfinite(py).all()):
            raise ValueError(f'Nonfinite result for {i}')
        xy, conf = P.rtm_decode({'pred_x': px, 'pred_y': py}, np.array(entry['matrix']))
        entry['joints_xy'] = xy.tolist()
        entry['joint_scores'] = conf.tolist()
        st = stats.setdefault(entry['clip'], {'frames': 0, 'joint_scores_ge_0.3': 0})
        st['frames'] += 1
        st['joint_scores_ge_0.3'] += int((conf >= .3).sum())
        im = cv2.imread(str(out / entry['image']))
        for u, v in P.COCO_BONES:
            if min(conf[u], conf[v]) >= .3:
                cv2.line(im, tuple(xy[u].astype(int)), tuple(xy[v].astype(int)), (40, 240, 40), 3, cv2.LINE_AA)
        for point, score in zip(xy, conf):
            cv2.circle(im, tuple(point.astype(int)), 4, (40, 240, 40) if score >= .3 else (0, 120, 255), -1)
        cv2.rectangle(im, (0, 0), (im.shape[1], 70), (20, 25, 25), -1)
        cv2.putText(im, f"{entry['clip']}  source {entry['source_time_s']:.2f}s | RTMPose on Ventuno", (15, 27), cv2.FONT_HERSHEY_SIMPLEX, .7, (255,255,255), 2)
        cv2.putText(im, 'Manual player crop | green score >=0.3, orange below | scores are not accuracy', (15, 55), cv2.FONT_HERSHEY_SIMPLEX, .6, (255,255,255), 1)
        dest = out / entry['clip'] / 'overlay_frames'
        dest.mkdir(exist_ok=True)
        cv2.imwrite(str(dest / f"{entry['index']:05d}.jpg"), im)
    for clip_id in stats:
        run(['ffmpeg', '-v', 'error', '-framerate', str(a.fps), '-i', str(out / clip_id / 'overlay_frames/%05d.jpg'),
             '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(out / f'{clip_id}_overlay.mp4')])
    report = {'serial': a.serial, 'model': MODEL, 'runner': RUNNER, 'board_directory': board,
              'frames': len(entries), 'fps_sampled': a.fps, 'manual_roi_normalized_cx_cy_height': ROIS,
              'model_inference_ms': {'count': len(latencies), 'mean': float(np.mean(latencies)) if latencies else None,
                                     'p95': float(np.percentile(latencies,95)) if latencies else None},
              'runner_wall_s': wall, 'peak_rss_mib': int(rss[1])/1024 if rss else None,
              'clips': stats, 'limitations': ['Manual fixed crop; no automatic detection/tracking tested.',
              'Mac performs decoding, cropping, and rendering; Ventuno runs RTMPose inference.',
              'No labeled keypoints; scores and successful execution are not accuracy.',
              'Edited/slow-motion footage; not capture-to-feedback throughput.']}
    (out / 'report.json').write_text(json.dumps(report, indent=2)+'\n')
    (out / 'keypoints.json').write_text(json.dumps({'joint_order': P.COCO17, 'frames': entries})+'\n')
    print(json.dumps(report, indent=2))
    print('OUTPUT:', out)


if __name__ == '__main__':
    main()
