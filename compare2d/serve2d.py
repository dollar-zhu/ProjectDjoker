"""Event detection and view estimation shared by the live 2D path and the projected reference.

Both sides call the same functions on canonical17 2D poses, so event semantics match by construction.
"""
import warnings
import numpy as np
from dms.contract import interior_angles

EVENT_DEFINITION = 'djoker-load-2d-v1'
SMOOTH_HALF_WINDOW_S = 1 / 24  # +/-41.7 ms, i.e. 5 frames at 60 fps
REACH_EXCLUDE_TAIL = 0.05
POST_REACH_CHECK_S = 0.2
DEEPER_TOLERANCE_DEG = 2.0
L_SH, R_SH, L_HIP, R_HIP, R_WRIST = 5, 6, 11, 12, 10

def smooth(times, values):
    """Centered moving average over a fixed time window; NaN-aware, works with variable frame rate."""
    values = np.asarray(values, float); out = np.full(values.shape, np.nan)
    for i, t in enumerate(times):
        window = values[np.abs(times - t) <= SMOOTH_HALF_WINDOW_S + 1e-9]
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)  # all-NaN columns (e.g. missing facial joints) stay NaN
            out[i] = np.nanmean(window, axis=0)
    return out

def detect_events(times, pose2d):
    """reach = highest smoothed right wrist (image up), excluding the last 5% of the clip;
    load = minimum smoothed mean knee angle before reach. Proxies, not contact or racket events."""
    times = np.asarray(times, float); n = len(times)
    angles = interior_angles(pose2d)
    height = smooth(times, -pose2d[:, R_WRIST, 1])
    # Compare the same two-knee quantity in every frame. A missing leg must
    # not turn the average into the other leg alone (an artificial minimum).
    paired = np.isfinite(angles[:, 2:4]).all(1)
    knee = smooth(times, np.mean(angles[:, 2:4], axis=1))
    knee[~paired] = np.nan
    last = max(2, int(np.floor((1 - REACH_EXCLUDE_TAIL) * (n - 1))))
    if not np.isfinite(height[:last + 1]).any():
        return None, None, angles, ['hitting_wrist_unavailable']
    reach = int(np.nanargmax(height[:last + 1]))
    flags = []
    if reach < 2: return None, reach, angles, ['reach_too_early']
    if not np.isfinite(knee[:reach]).any():
        return None, reach, angles, ['no_complete_knee_pair']
    load = int(np.nanargmin(knee[:reach]))
    if load == 0: flags.append('load_at_clip_start')
    if load == reach - 1: flags.append('load_adjacent_to_reach')
    if reach == last: flags.append('reach_at_search_boundary')
    # Fail closed: knees still bending after the wrist peak means the peak preceded loading
    # (e.g. a mislabelled or toss-arm wrist), so the load estimate is not trustworthy.
    after = (times > times[reach]) & (times <= times[reach] + POST_REACH_CHECK_S)
    if np.isfinite(knee[after]).any() and np.nanmin(knee[after]) < knee[load] - DEEPER_TOLERANCE_DEG:
        return None, reach, angles, flags + ['deeper_knee_flexion_after_reach']
    return load, reach, angles, flags

def hip_width_ratio(pose2d_frame):
    """Apparent hip width / apparent trunk length in one 2D frame."""
    p = np.asarray(pose2d_frame, float)
    hip = np.linalg.norm(p[L_HIP] - p[R_HIP])
    trunk = np.linalg.norm((p[L_SH] + p[R_SH]) / 2 - (p[L_HIP] + p[R_HIP]) / 2)
    return hip / trunk if trunk > 0 else np.nan

def estimate_yaw(ratio_observed, ratio_full_width):
    """Camera obliquity from the profile view, in [0, 90] degrees (orthographic, level camera).
    0 = looking along the hip line (hips overlap, knee bend in the image plane)."""
    return float(np.degrees(np.arcsin(np.clip(ratio_observed / ratio_full_width, 0, 1))))

METRICS = {  # name -> (units, description); all projected 2D, front/back assume a right-handed server
    'front_knee_at_load': ('deg', 'left knee interior angle at deepest bend'),
    'back_knee_at_load': ('deg', 'right knee interior angle at deepest bend'),
    'bend_duration': ('s', 'time from mean knee angle last above 150 deg to deepest bend'),
    'extend_duration': ('s', 'time from deepest bend until mean knee angle first exceeds 160 deg'),
    'front_knee_drive_speed': ('deg/s', 'peak front-knee straightening speed within 350 ms after deepest bend'),
    'load_to_reach': ('s', 'time from deepest bend to highest right wrist (contact proxy)'),
    # Hitting (right) arm. Body-only proxies: no racket, hand orientation or pronation. Racket drop is not
    # compared: in 2D the trophy and drop folds look alike and the reference is unstable there (see docs).
    'trophy_upperarm_elevation': ('deg', 'right elbow-shoulder-hip angle at deepest bend (trophy): how high the hitting elbow is lifted'),
    'trophy_toss_height': ('torso', 'left wrist height above shoulder midpoint at deepest bend, in trunk lengths'),
    'arm_fold_lead': ('s', 'how long before the deepest bend the hitting elbow folds below 45 deg and stays folded (arm-leg timing)'),
    'contact_elbow_extension': ('deg', 'hitting elbow angle at contact proxy'),
    'contact_hand_height': ('torso', 'hitting wrist height above shoulders at contact proxy'),
}
FOLD_DEG = 45.0
FOLD_LOOKBACK_S = 0.8

def serve_metrics(times, pose2d):
    """Shared per-serve metrics; None when the load event fails closed."""
    times = np.asarray(times, float)
    load, reach, angles, flags = detect_events(times, pose2d)
    if load is None: return None
    s = smooth(times, angles); knee = np.mean(s[:, 2:4], 1)
    above = np.flatnonzero(knee[:load] > 150); start = above[-1] if len(above) else 0
    up = np.flatnonzero(knee[load:] > 160)
    drive = np.gradient(s[:, 2], times); window = (times > times[load]) & (times <= times[load] + 0.35)
    return {'load_frame': load, 'reach_frame': reach, 'flags': flags, 'values': {
        'front_knee_at_load': float(angles[load, 2]), 'back_knee_at_load': float(angles[load, 3]),
        'bend_duration': float(times[load] - times[start]),
        'extend_duration': float(times[load + up[0]] - times[load]) if len(up) else None,
        'front_knee_drive_speed': float(np.nanmax(drive[window])) if window.any() else None,
        'load_to_reach': float(times[reach] - times[load]), **arm_metrics(times, smooth(times, pose2d), angles, load, reach)}}

def arm_metrics(times, s, angles, load, reach):
    """Right-handed hitting-arm metrics from the smoothed pose s; None where a joint is missing."""
    sh = (s[:, L_SH] + s[:, R_SH]) / 2; hip = (s[:, L_HIP] + s[:, R_HIP]) / 2; trunk = np.linalg.norm(sh - hip, axis=1)
    height = lambda j, i: float((sh[i, 1] - s[i, j, 1]) / trunk[i]) if np.isfinite(s[i, j]).all() and trunk[i] > 0 else None
    sa = smooth(times, angles); elbow = sa[:, 1]; num = lambda v: float(v) if np.isfinite(v) else None
    window = [i for i in range(len(times)) if times[load] - FOLD_LOOKBACK_S <= times[i] <= times[load]]
    onset = next((i for i in window if np.all(elbow[i:load + 1] < FOLD_DEG)), None)
    return {'trophy_upperarm_elevation': num(sa[load, 5]), 'trophy_toss_height': height(9, load),
            'arm_fold_lead': float(times[load] - times[onset]) if onset is not None else (0.0 if np.isfinite(elbow[load]) else None),
            'contact_elbow_extension': num(sa[reach, 1]), 'contact_hand_height': height(R_WRIST, reach)}
