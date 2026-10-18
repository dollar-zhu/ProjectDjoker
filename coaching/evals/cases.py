"""Eval inputs for the spoken-feedback phrasing step.

Each case is a full Feedback dict produced by the real rule engine (`select` + `feedback`), so the model sees exactly
what the device would send. Synthetic cases perturb Djokovic's reference medians at one camera view to trigger each
rule; the real case runs the Serve1 packet end to end when it is present under runs/dev/.
"""
import json
from pathlib import Path
from coaching.board_feedback import ROOT, decide, feedback, load_rating, select
from coaching.rating import rate_with_view_sensitivity, not_rated

REFERENCE = ROOT / 'reference/projected2d/board_reference.json'
RULES = ROOT / 'coaching/rules.json'
SERVE1 = ROOT / 'runs/dev/serve1/dms/serve1.json'
YAW = 15

# (id, what the serve looks like, metric overrides relative to the reference row, reference allowed)
# Overrides: ('median', +d) offsets the median; ('p10', -d) etc. offsets a percentile; a bare number is absolute.
SCENARIOS = [
    ('reference_like', 'Djokovic-like serve: no correction, praise for drive and reach', {}, True),
    ('front_leg', 'Front knee straighter, back knee deeper than reference; good drive',
     {'front_knee_at_load': ('median', 12), 'back_knee_at_load': ('median', -10)}, True),
    ('front_leg_borderline', 'Front-leg pattern just over the 6 degree threshold; weak drive',
     {'front_knee_at_load': ('median', 6.5), 'back_knee_at_load': ('median', -6.5), 'front_knee_drive_speed': ('p10', -60)}, True),
    ('shallow_both', 'Both knees straighter than reference; weak drive',
     {'front_knee_at_load': ('median', 15), 'back_knee_at_load': ('median', 15), 'front_knee_drive_speed': ('p10', -80)}, True),
    ('shallow_with_reach', 'Both knees straighter; reach at contact is good',
     {'front_knee_at_load': ('median', 18), 'back_knee_at_load': ('median', 12), 'front_knee_drive_speed': ('p10', -50)}, True),
    ('shallow_extreme', 'Nearly straight legs at the bottom of the load',
     {'front_knee_at_load': ('median', 35), 'back_knee_at_load': ('median', 30), 'front_knee_drive_speed': ('p10', -150)}, True),
    ('trophy_elbow_low', 'Hitting elbow low in the trophy position; good drive',
     {'trophy_upperarm_elevation': ('p25', -15)}, True),
    ('trophy_elbow_low_no_praise', 'Low trophy elbow, weak drive and short reach',
     {'trophy_upperarm_elevation': ('p25', -25), 'front_knee_drive_speed': ('p10', -60), 'contact_elbow_extension': ('p10', -20)}, True),
    ('arm_early', 'Hitting arm folds well before the knee bend',
     {'arm_fold_lead': ('p75', 0.12)}, True),
    ('tempo_rushed', 'Knee bend is a quick late drop',
     {'bend_duration': ('p10', -0.12), 'front_knee_drive_speed': ('p10', -40)}, True),
    ('tempo_with_drive', 'Quick late drop, but leg drive is good',
     {'bend_duration': ('p10', -0.1)}, True),
    ('multiple_faults', 'Front-leg pattern plus low elbow and early arm; only one cue may be spoken',
     {'front_knee_at_load': ('median', 14), 'back_knee_at_load': ('median', -12), 'trophy_upperarm_elevation': ('p25', -12),
      'arm_fold_lead': ('p75', 0.1)}, True),
    ('strict_mode', 'Reference comparison blocked (strict mode): descriptive observation only',
     {'front_knee_at_load': ('median', 12), 'back_knee_at_load': ('median', -10)}, False),
]


def _metrics(row, overrides):
    metrics = {k: v['median'] for k, v in row.items() if isinstance(v, dict) and 'median' in v}
    for name, change in overrides.items():
        metrics[name] = change if isinstance(change, (int, float)) else row[name][change[0]] + change[1]
    return metrics


def build():
    ref = json.loads(REFERENCE.read_text()); rules = json.loads(RULES.read_text()); rating_cfg = load_rating(RULES)
    by_id = {r['id']: r for r in rules['rules']}
    table = ref['table']['all']; row = min(table, key=lambda r: abs(r['yaw_deg'] - YAW))
    cases = []
    for case_id, description, overrides, reference_ok in SCENARIOS:
        metrics = _metrics(row, overrides)
        cue, secondary, praise = select(metrics, row, rules, reference_ok)
        rating = rate_with_view_sensitivity(metrics, table, YAW, rating_cfg) if reference_ok else not_rated('reference_blocked', rating_cfg)
        fb = feedback(case_id, cue, metrics, row if reference_ok else None, [] if reference_ok else ['reference_unvalidated'],
                      [], rules, praise, demo=reference_ok, rating=rating, rating_cfg=rating_cfg)
        fb['secondary_findings'] = secondary
        cases.append({'id': case_id, 'description': description, 'source': 'synthetic', 'feedback': fb})
    cases.append({'id': 'retry_capture', 'description': 'Tracking too poor to judge the serve', 'source': 'synthetic',
                  'feedback': feedback('retry_capture', by_id['retry_capture'], {}, None, ['low_joint_confidence'], [], rules, None,
                                       rating=not_rated('retry_capture', rating_cfg), rating_cfg=rating_cfg)})
    if SERVE1.exists():
        cases.append({'id': 'serve1_real', 'description': 'Real recorded serve (Serve1), unvalidated demo mode', 'source': 'real',
                      'feedback': decide(SERVE1, REFERENCE, RULES, allow_unvalidated_reference=True)})
    return cases


if __name__ == '__main__':
    for c in build():
        fb = c['feedback']
        print(f"{c['id']:28s} {fb['rule_id']:32s} praise={fb['praise_rule_id']} score={(fb['rating'] or {}).get('score')}")
