"""Compare a 2D DMS serve packet with the projected Djokovic 2D reference (knee loading).

Production output fails closed: without validation records it returns insufficient_evidence with null deltas.
Measured numbers go to a separate diagnostic report marked unvalidated.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from dms.contract import load_packet
from . import VERSION
from .serve2d import detect_events, hip_width_ratio, estimate_yaw, smooth, EVENT_DEFINITION

ROOT = Path(__file__).resolve().parents[1]
KNEE_CHAIN = [11, 13, 15, 12, 14, 16]
GATES = {'max_view_yaw_deg': 30, 'min_joint_score': 0.5, 'prd_joint_score': 0.8, 'min_consecutive_frames': 5,
         'max_gap_ms': 200, 'min_reference_serves': 3}

def longest_run(mask):
    best = run = 0
    for ok in mask: run = run + 1 if ok else 0; best = max(best, run)
    return best

def quality(times, conf, load, threshold):
    """Knee-chain scores around the load event: at the event, and the longest passing run within +/-150 ms."""
    near = np.flatnonzero(np.abs(times - times[load]) <= 0.15)
    passing = (conf[near][:, KNEE_CHAIN] >= threshold).all(1)
    gaps = np.diff(times[near]) * 1000
    return {'threshold': threshold, 'at_event_min_score': float(np.nanmin(conf[load, KNEE_CHAIN])),
            'at_event_pass': bool((conf[load, KNEE_CHAIN] >= threshold).all()),
            'longest_passing_run_frames': longest_run(passing), 'max_gap_ms_near_event': float(gaps.max()) if len(gaps) else None}

def compare(packet_path, reference_path, serve_type='unknown'):
    meta, arrays = load_packet(packet_path)
    ref = json.loads(Path(reference_path).read_text())
    pose, conf, times = arrays['pose'], arrays['joint_confidence'], arrays['timestamps']
    reasons, diag = [], {'status': 'unvalidated_diagnostic', 'version': VERSION}
    if meta['features']['representation'] != ref['representation']: reasons.append('representation_mismatch')
    if meta['source']['coordinate_system'] != 'image_2d': reasons.append('coordinate_system_not_image_2d')
    if meta['handedness'] != ref['source']['handedness_assumed']: reasons.append('handedness_unknown_or_mismatch')
    load, reach, angles, flags = detect_events(times, pose)
    if load is None:
        reasons.append('load_event_not_found')
        return {'status': 'insufficient_evidence', 'reasons': reasons, 'delta': None}, None
    at_load = smooth(times, pose)[load]; ratio = hip_width_ratio(at_load)
    # Sign assumes the camera is behind the server (protocol): left hip right of right hip in the image = positive yaw.
    side = np.sign(at_load[11, 0] - at_load[12, 0]) or 1.0
    yaw = side * estimate_yaw(ratio, ref['hip_width_over_trunk_3d_median'])
    if abs(yaw) > GATES['max_view_yaw_deg']: reasons.append('view_outside_supported_band')
    q = quality(times, conf, load, GATES['min_joint_score']); q_prd = quality(times, conf, load, GATES['prd_joint_score'])
    if not q['at_event_pass'] or q['longest_passing_run_frames'] < GATES['min_consecutive_frames']: reasons.append('low_joint_confidence')
    if q['max_gap_ms_near_event'] is not None and q['max_gap_ms_near_event'] > GATES['max_gap_ms']: reasons.append('sampling_gap_near_event')
    group = {'1': 'first_serve', '2': 'second_serve'}.get(serve_type, 'all')
    grid = ref['camera_model']['yaw_grid_deg']; yi = int(np.argmin(np.abs(np.array(grid) - yaw)))
    summary = ref['summary'][group][yi]
    if summary['n'] < GATES['min_reference_serves']: reasons.append('too_few_reference_serves')
    user = [float(angles[load, 2]), float(angles[load, 3])]
    ref_values = np.array([r['by_yaw'][yi]['knee_2d_at_load'] for r in ref['records']
                           if r['by_yaw'][yi]['knee_2d_at_load'] is not None and (group == 'all' or r['serve_number'] == int(serve_type))])
    # Evidence the PRD requires before any production delta; none of these records exist yet.
    blocking = reasons + ['reference_mapping_provisional', 'reference_events_unvalidated', 'user_event_unvalidated', 'camera_profile_unvalidated']
    if group == 'all': blocking.append('serve_type_unknown_subtype_comparison_blocked')
    sens = {}
    for d in (-10, 10):
        j = int(np.argmin(np.abs(np.array(grid) - np.clip(yaw + d, -90, 90))))
        sens[f'{d:+d}deg'] = {'yaw_deg': grid[j], 'reference_median': ref['summary'][group][j]['median']}
    production = {
        'status': 'insufficient_evidence', 'reasons': blocking, 'metric': 'knee_interior_angle_2d_at_load', 'phase': 'loading',
        'user_value': None, 'reference_median': None, 'reference_range': None, 'delta': None, 'units': 'degrees',
        'eligible_reference_count': summary['n'], 'reference_group': group, 'validation_ids': [], 'feedback_allowed': False}
    diag.update({
        'shot_id': meta['shot_id'], 'event_definition': EVENT_DEFINITION, 'columns': ['left_knee', 'right_knee'],
        'events': {'load': {'frame': load, 'time_s': float(times[load]), 'validated': False},
                   'reach': {'frame': reach, 'time_s': float(times[reach]), 'validated': False,
                             'note': 'highest right wrist proxy, not ball contact'}, 'flags': flags},
        'view': {'hip_width_over_trunk_2d': float(ratio), 'reference_full_width_ratio_3d': ref['hip_width_over_trunk_3d_median'],
                 'estimated_yaw_deg': yaw, 'reference_yaw_used_deg': grid[yi],
                 'sign_assumption': 'camera behind the server; positive = left hip appears right of right hip',
                 'caveat': 'COCO and H36M hip landmarks differ; level orthographic camera assumed'},
        'user_knee_at_load': user,
        'reference': {'group': group, 'n': summary['n'], 'median': summary['median'], 'p10': summary['p10'], 'p90': summary['p90'],
                      'percentile_of_user': [float((ref_values[:, i] < user[i]).mean() * 100) for i in range(2)]},
        'delta_user_minus_reference_median': [user[i] - summary['median'][i] for i in range(2)],
        'yaw_sensitivity': sens, 'quality': {'gate': q, 'prd_threshold': q_prd},
        'gate_reasons_excluding_missing_validation': reasons, 'production_status': production['status'],
        'interpretation': 'Larger angle = straighter knee. Exemplar comparison of one serve; not a technique score or ranking.'})
    return production, diag

def plot(packet_path, reference_dir, diag, out_dir, video=None, crop=None):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    meta, arrays = load_packet(packet_path)
    t = np.load(Path(reference_dir) / 'djokovic_knee_traces_2d.npz')
    yi = list(t['yaws']).index(diag['view']['reference_yaw_used_deg'])
    load = diag['events']['load']['frame']; times = arrays['timestamps'] - arrays['timestamps'][load]
    user_angles = arrays['features']
    grid = np.arange(-0.8, 0.6001, 1 / 60)
    REF, USER, INK, MUTED = '#2a78d6', '#eb6834', '#0b0b0b', '#52514e'
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for c, (ax, name) in enumerate(zip(axes, ['Left (front) knee', 'Right (back) knee'])):
        curves = []
        for s in range(len(t['traces'])):
            k = int(t['load_frame'][s, yi])
            if k < 0: continue
            if diag['reference']['group'] != 'all' and t['serve_number'][s] != int(diag['reference']['group'] == 'second_serve') + 1: continue
            tr = t['traces'][s, yi, :, c]; n = np.isfinite(tr).sum(); tt = np.arange(n) / float(t['fps']) - k / float(t['fps'])
            curves.append(np.interp(grid, tt, tr[:n], left=np.nan, right=np.nan))
        curves = np.array(curves); cnt = np.isfinite(curves).sum(0); ok = cnt >= 10
        lo, med, hi = (np.where(ok, np.nanpercentile(curves, p, axis=0), np.nan) for p in (10, 50, 90))
        ax.fill_between(grid, lo, hi, color=REF, alpha=0.18, linewidth=0, label='Djokovic 10th–90th pct')
        ax.plot(grid, med, color=REF, lw=2, label=f"Djokovic median (n={diag['reference']['n']})")
        ax.plot(times, user_angles[:, 2 + c], color=USER, lw=2, marker='o', ms=3, label=f"{meta['shot_id']} (this serve)")
        ax.axvline(0, color=MUTED, lw=1, ls=':')
        u, r = diag['user_knee_at_load'][c], diag['reference']['median'][c]
        ax.annotate(f"{u:.0f}°", (0, u), xytext=(-8, 8 if u > r else -16), textcoords='offset points', ha='right', color=INK, fontsize=10)
        ax.annotate(f"{r:.0f}°", (0, r), xytext=(8, 8 if r >= u else -16), textcoords='offset points', color=INK, fontsize=10)
        ax.set_title(name, color=INK, fontsize=11, loc='left'); ax.set_xlabel('seconds from deepest knee bend', color=MUTED)
        ax.set_xlim(grid[0], grid[-1]); ax.grid(axis='y', color='#e6e5e1', lw=0.8); ax.set_axisbelow(True)
        for side in ('top', 'right'): ax.spines[side].set_visible(False)
        ax.tick_params(colors=MUTED)
    axes[0].set_ylabel('2D knee interior angle (°, 180 = straight)', color=MUTED)
    axes[1].legend(frameon=False, fontsize=9, loc='lower right')
    fig.suptitle(f"Knee loading, projected 2D at {diag['view']['reference_yaw_used_deg']}° from profile view — "
                 "UNVALIDATED diagnostic, development host", fontsize=10, color=MUTED, x=0.01, ha='left')
    fig.tight_layout(); fig.savefig(out_dir / 'knee_vs_djokovic.png', dpi=150); plt.close(fig)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('packet', type=Path)
    p.add_argument('--reference', type=Path, default=ROOT / 'reference/projected2d')
    p.add_argument('--serve-type', choices=['1', '2', 'unknown'], default='unknown')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    production, diag = compare(a.packet, a.reference / 'djokovic_knee_load_2d.json', a.serve_type)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'comparison.json').write_text(json.dumps(production, indent=2) + '\n')
    if diag:
        (a.out / 'diagnostic.json').write_text(json.dumps(diag, indent=2) + '\n')
        plot(a.packet, a.reference, diag, a.out)
    print(json.dumps({'production': production, 'diagnostic': diag}, indent=1))

if __name__ == '__main__':
    main()
