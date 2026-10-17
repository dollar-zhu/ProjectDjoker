"""Offline: project the 88 Djokovic 3D serves into level orthographic cameras and summarize 2D knee loading.

Yaw is measured from the profile view: 0 deg looks along the server's hip line at the 3D deepest-knee frame.
The source layout is the provisional H36M interpretation; every output inherits that status.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from . import VERSION
from .serve2d import detect_events, serve_metrics, METRICS, EVENT_DEFINITION

ROOT = Path(__file__).resolve().parents[1]
YAWS = np.arange(-90, 91, 5)
PROFILE = int(np.flatnonzero(YAWS == 0)[0])
FPS = 60.0  # n_frames / duration_sec in metadata: 59.998-60.002 for all 88 serves
# Provisional H36M index for each canonical17 slot; facial joints stay missing.
H36M_TO_CANONICAL = [None, None, None, None, None, 11, 14, 12, 15, 13, 16, 4, 1, 5, 2, 6, 3]

def unmirror(p3):
    """The export matches mmpose's demo transform (x -> -x, y/z swap, z -> -z), a reflection.
    Negating x restores real-world chirality; interior angles are unchanged."""
    q = np.array(p3, float); q[..., 0] *= -1
    return q

def chirality(p3):
    """Median cosine between nose direction and hip-implied facing (h x up); positive = proper frame."""
    h = p3[:, 4] - p3[:, 1]; h[:, 2] = 0; facing = np.cross(h, [0, 0, 1])
    nose = p3[:, 9] - p3[:, 8]; nose[:, 2] = 0
    return float(np.nanmedian((facing * nose).sum(1) / np.linalg.norm(facing, axis=1) / np.linalg.norm(nose, axis=1)))

def to_canonical(p3):
    out = np.full((len(p3), 17, 3), np.nan)
    for c, h in enumerate(H36M_TO_CANONICAL):
        if h is not None: out[:, c] = p3[:, h]
    return out

def project(p3c, hip_angle, yaw_deg):
    """Level orthographic camera; returns image-style (x right, y down) 2D coordinates."""
    th = hip_angle + np.radians(yaw_deg)
    view = np.array([np.cos(th), np.sin(th), 0.0]); right = np.cross(view, [0, 0, 1])
    return np.stack([p3c @ right, -p3c[..., 2]], axis=-1)

def build(project_root, out_dir):
    import pandas as pd  # offline builder only; the board never imports pandas
    sys.path.insert(0, str(project_root / 'reference'))
    from analyze import angles as angles3d, events as events3d
    source = project_root / 'reference/source/data'
    meta = pd.read_parquet(source / 'metadata.parquet')
    rows = meta[meta.server.eq('Novak Djokovic')].sort_values('filename')
    manifest = {r['filename']: r['sha256'] for r in json.loads((project_root / 'reference/results/manifest.json').read_text())}
    if len(rows) != 88: raise RuntimeError('Expected 88 Djokovic serves')
    records, traces = [], np.full((len(rows), len(YAWS), 120, 2), np.nan)
    for s, row in enumerate(rows.itertuples()):
        path = source / 'keypoints' / row.filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest[row.filename]: raise RuntimeError(f'{row.filename}: checksum differs')
        raw = np.load(path).astype(float); p3 = unmirror(raw); n = len(p3)
        a3 = angles3d(p3); ev3, _ = events3d(p3, a3); k3 = int(ev3[1])
        hip = p3[k3, 4, :2] - p3[k3, 1, :2]; hip_angle = float(np.arctan2(hip[1], hip[0]))
        trunk3 = np.linalg.norm((p3[k3, 11] + p3[k3, 14]) / 2 - (p3[k3, 4] + p3[k3, 1]) / 2)
        times = np.arange(n) / FPS; p3c = to_canonical(p3)
        rec = {'filename': row.filename, 'sha256': manifest[row.filename], 'serve_number': int(row.serve_number),
               'frames': n, 'load_3d_frame': k3, 'knee_3d_at_load_3d': [float(a3[k3, 6]), float(a3[k3, 7])],
               'hip_width_over_trunk_3d': float(np.linalg.norm(p3[k3, 4] - p3[k3, 1]) / trunk3),
               'chirality_raw': chirality(raw), 'chirality_unmirrored': chirality(p3), 'by_yaw': []}
        for y, yaw in enumerate(YAWS):
            p2 = project(p3c, hip_angle, yaw)
            load, reach, a2, flags = detect_events(times, p2)
            traces[s, y, :n] = a2[:, 2:4]
            m = serve_metrics(times, p2)
            rec['by_yaw'].append({'yaw_deg': int(yaw), 'load_frame': load, 'reach_frame': reach, 'flags': flags,
                                  'knee_2d_at_load': None if load is None else [float(a2[load, 2]), float(a2[load, 3])],
                                  'metrics': None if m is None else m['values']})
        records.append(rec)

    def summary(subset):
        out = []
        for y, yaw in enumerate(YAWS):
            v = np.array([r['by_yaw'][y]['knee_2d_at_load'] for r in subset if r['by_yaw'][y]['knee_2d_at_load'] is not None])
            q = lambda pct: np.round(np.percentile(v, pct, axis=0), 2).tolist()
            out.append({'yaw_deg': int(yaw), 'n': len(v), 'median': q(50), 'p10': q(10), 'p90': q(90)})
        return out
    groups = {'all': records, 'first_serve': [r for r in records if r['serve_number'] == 1],
              'second_serve': [r for r in records if r['serve_number'] == 2]}
    agree = [abs(r['by_yaw'][PROFILE]['load_frame'] - r['load_3d_frame']) <= 3 for r in records if r['by_yaw'][PROFILE]['load_frame'] is not None]
    excluded = {int(y): [r['filename'] for r in records if r['by_yaw'][i]['load_frame'] is None] for i, y in enumerate(YAWS)}
    result = {
        'version': VERSION, 'event_definition': EVENT_DEFINITION, 'metric': 'knee_interior_angle_2d_at_load',
        'columns': ['left_knee', 'right_knee'], 'units': 'degrees', 'representation': 'projected_2d',
        'camera_model': {'type': 'orthographic', 'pitch_deg': 0, 'yaw_reference': 'hip line (H36M L-R hip) at 3D deepest-knee frame',
                         'yaw_grid_deg': YAWS.tolist(), 'yaw_meaning': '0 = camera behind the right hip looking along the hip line (profile); |90| = square-on; '
                                        'positive yaw = left hip appears to the right of the right hip in the image',
                         'chirality': 'source x negated before projection (mmpose demo reflection undone)'},
        'timebase': {'fps': FPS, 'source': 'metadata n_frames/duration_sec'},
        'source': {'player': 'Novak Djokovic', 'handedness_assumed': 'right', 'serves': len(records),
                   'joint_mapping': 'provisional H36M -> canonical17 (facial joints missing)', 'mapping_validated': False,
                   'upstream_pipeline': 'RTMDet + RTMPose 2D -> MotionBERT 3D (upstream README); mmpose demo output transform observed',
                   'upstream_commit': '7889457cc9b50b0c2a9fdcc81d786bcdb6b8652c'},
        'hip_width_over_trunk_3d_median': float(np.median([r['hip_width_over_trunk_3d'] for r in records])),
        'diagnostics': {'chirality_positive_raw': f"{sum(r['chirality_raw'] > 0 for r in records)}/88",
                        'chirality_positive_unmirrored': f"{sum(r['chirality_unmirrored'] > 0 for r in records)}/88",'profile_view_2d_load_within_3_frames_of_3d_load': f'{sum(agree)}/{len(agree)} valid serves'},
        'exclusions_by_yaw': excluded,
        'summary': {k: summary(v) for k, v in groups.items()},
        'validation': {'status': 'unvalidated', 'validation_id': None,
                       'limitations': ['Reference 3D is itself estimated from broadcast video', 'Joint mapping provisional',
                                       'Events are body-landmark proxies without video confirmation', 'Level orthographic camera assumed']},
        'records': records,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'djokovic_knee_load_2d.json').write_text(json.dumps(result, indent=1) + '\n')
    np.savez_compressed(out_dir / 'djokovic_knee_traces_2d.npz', traces=traces, yaws=YAWS, fps=FPS,
                        serve_number=np.array([r['serve_number'] for r in records]),
                        load_frame=np.array([[b['load_frame'] if b['load_frame'] is not None else -1 for b in r['by_yaw']] for r in records]))
    write_board_reference(result, groups, out_dir)
    return result

def write_board_reference(result, groups, out_dir):
    """Compact lookup table for the device: per serve group, per yaw, per metric median/p10/p90/n."""
    table = {}
    for g, subset in groups.items():
        table[g] = []
        for y, yaw in enumerate(YAWS):
            row = {'yaw_deg': int(yaw)}
            for name in METRICS:
                v = np.array([r['by_yaw'][y]['metrics'][name] for r in subset
                              if r['by_yaw'][y]['metrics'] and r['by_yaw'][y]['metrics'][name] is not None], float)
                row[name] = dict(n=len(v), median=round(float(np.median(v)), 3),
                                 **{f'p{q}': round(float(np.percentile(v, q)), 3) for q in (10, 25, 75, 90)}) if len(v) else None
            table[g].append(row)
    board = {'version': VERSION, 'reference_id': 'djokovic-usopen2024-projected2d-v0.1', 'player': 'Novak Djokovic',
             'event_definition': EVENT_DEFINITION, 'representation': 'projected_2d', 'handedness': 'right',
             'metrics': {k: {'units': u, 'definition': d} for k, (u, d) in METRICS.items()},
             'camera_model': result['camera_model'], 'hip_width_over_trunk_full': result['hip_width_over_trunk_3d_median'],
             'validation': result['validation'], 'table': table}
    (out_dir / 'board_reference.json').write_text(json.dumps(board, separators=(',', ':')) + '\n')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, default=ROOT)
    p.add_argument('--out', type=Path, default=ROOT / 'reference/projected2d')
    r = build(p.parse_args().project, p.parse_args().out)
    for y in (-30, -15, 0, 15, 30, 45, 90):
        s = r['summary']['all'][(y + 90) // 5]; print(f"yaw {y:2d}: median L/R {s['median']}  p10 {s['p10']}  p90 {s['p90']}  n={s['n']}")
    print(r['diagnostics'], 'hip/trunk 3D median', round(r['hip_width_over_trunk_3d_median'], 3))

if __name__ == '__main__':
    main()
