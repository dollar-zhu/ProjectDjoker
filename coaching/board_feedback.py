"""Board-side serve feedback: DMS packet + compact reference + rules -> one Feedback decision and a Qwen request.

Mirrors what the device does after the completion trigger; needs only numpy and the DMS package.
The phrasing model (Gemma 4 E2B) may only add praise and linking words around the approved cue (`coach_request`);
`validate` checks its reply and falls back to canonical speech. `qwen_request` is the earlier free-rephrase prompt, kept for evals.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from dms.contract import load_packet
from compare2d.serve2d import serve_metrics, hip_width_ratio, estimate_yaw, smooth
from compare2d.compare import quality, GATES
from .rating import rate_with_view_sensitivity, not_rated

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT = (
    "You are the voice of an offline tennis serve coaching device. The player just finished a serve and will hear your "
    "words through a speaker. Rewrite the APPROVED feedback in the user message as one short, natural spoken message.\n"
    "Rules:\n"
    "- At most {max_words} words. Plain, encouraging language a player can act on before the next serve.\n"
    "- Use only the facts, praise and cue provided. Do not add new advice, drills, body parts or numbers.\n"
    "- If you mention numbers, use only values listed in allowed_numbers. Numbers are optional.\n"
    "- If score is not null, say it once as \"Score N.\" at the start. It is a 0-100 similarity to Djokovic's typical range, not a quality grade.\n"
    "- Keep at most one actionable cue: the provided cue.\n"
    "- Never mention injury, pain, serve speed, the ball's flight, the racket, scores, or that copying Djokovic guarantees improvement.\n"
    "- Respond with JSON only: {{\"speech\": \"...\"}}"
)
# Coach voice (v2, v3). Small on-device models (Gemma 1-2B) follow worked examples far better than rule lists, so the
# rules stay short and the examples carry the style. Example cues are deliberately outside the rule set (toss arm,
# landing): if a model copies one into a reply, the topic check rejects it. Measurements and reference values are not sent.
# v3 (default): evals showed paraphrased cues drift into new advice ("keep your back knee tucked"), so the model now
# only adds praise and a few linking words; coaching content lives in the rules' canonical_speech.
COACH_PROMPTS = {
    'v2': ("You are a friendly tennis coach. A player just hit a serve and hears you through a small speaker. "
           "Say the coaching note out loud in your own words.\n"
           "- One or two short sentences, at most {max_words} words.\n"
           "- If there is praise, say it first, briefly.\n"
           "- Then the cue: keep its body parts and timing, phrased as one thing to feel on the next serve.\n"
           "- No numbers, angles or degrees. Do not mention Djokovic or any other player.\n"
           "- Never add advice, body parts or reasons that are not in the note.\n"
           "- Only if the note has a Score line, start with \"Score N.\" using that number.\n"
           "Reply with JSON only: {{\"speech\": \"...\"}}",
           [("Score: 72\nPraise: Good leg drive.\nCue: Keep your tossing arm up a moment longer.",
             '{"speech": "Score 72. Great push from the legs. Next one, leave that tossing arm up a beat longer."}'),
            ("Cue: Land on your front foot after contact.",
             '{"speech": "Let your weight carry you through so you land on your front foot after contact."}'),
            ("Cue: none", '{"speech": "Got that one. Ready for the next serve when you are."}')]),
    'v3': ("You are a friendly tennis coach. A player just hit a serve and hears you through a small speaker.\n"
           "- If there is praise, say it first in a few warm words.\n"
           "- Then say the cue almost word for word. You may add a short lead-in such as \"Next one,\".\n"
           "- If there is no praise, do not invent any; start with the cue.\n"
           "- If there is a Score line, start with \"Score N.\" using that number. Say no other numbers.\n"
           "- At most {max_words} words. Add nothing else.\n"
           "Reply with JSON only: {{\"speech\": \"...\"}}",
           [("Score: 72\nPraise: Good leg drive.\nCue: Keep your tossing arm up a moment longer.",
             '{"speech": "Score 72. Great push from the legs. Next one, keep your tossing arm up a moment longer."}'),
            ("Cue: Land on your front foot after contact.",
             '{"speech": "Next one, land on your front foot after contact."}'),
            ("Praise: Good reach at contact.\nCue: Turn your chest to the side as you toss.",
             '{"speech": "Nice full reach. Now turn your chest to the side as you toss."}')]),
}
PRAISE_WORDS = re.compile(r'\b(good|great|nice|well done|excellent|perfect|solid)\b', re.I)
PRO_NAMES = re.compile(r'djokovic|novak|sinner|federer|nadal|alcaraz|\bpros?\b', re.I)

# Any of these words in Qwen's speech must already appear in the approved praise/observation/cue text.
TOPIC_WORDS = ['knee', 'leg', 'hip', 'shoulder', 'elbow', 'wrist', 'arm', 'trunk', 'chest', 'head', 'foot', 'feet', 'ankle',
               'toss', 'jump', 'land', 'swing', 'contact', 'stance', 'weight', 'balance']
BANNED = re.compile(r'injur|pain|hurt|mph|km/?h|kilomet|speed of (the|your) serve|guarantee|racket|racquet', re.I)

def evaluate(rule, metrics, ref_row):
    for name, op, value in rule['condition']['all']:
        user = metrics.get(name); ref = ref_row.get(name) if ref_row else None
        if user is None or (op != 'none' and ref is None and rule['mode'] == 'reference'): return False
        if op == 'delta_ge' and not user - ref['median'] >= value: return False
        if op == 'delta_le' and not user - ref['median'] <= value: return False
        if op == 'below_p10' and not user < ref['p10']: return False
        if op == 'within_p10_p90' and not ref['p10'] <= user <= ref['p90']: return False
        if op == 'below_p25_by' and not user < ref['p25'] - value: return False
        if op == 'above_p75_by' and not user > ref['p75'] + value: return False
    return all(metrics.get(m) is not None for m in rule['requires'])

def fill(template, metrics, ref_row):
    if template is None: return None
    ns = {k: SimpleNamespace(user=v, ref=(ref_row or {}).get(k, {}) and ref_row[k]['median']) for k, v in metrics.items() if v is not None}
    return template.format(**ns)

def load_rating(rules_path, rating_path=None):
    path = Path(rating_path) if rating_path else Path(rules_path).with_name('rating.json')
    return json.loads(path.read_text()) if path.exists() else None

def decide(packet_path, reference_path, rules_path, serve_type='unknown', allow_unvalidated_reference=False, rating_path=None):
    meta, arrays = load_packet(packet_path)
    ref = json.loads(Path(reference_path).read_text()); rules = json.loads(Path(rules_path).read_text())
    rating_cfg = load_rating(rules_path, rating_path)
    pose, conf, times = arrays['pose'], arrays['joint_confidence'], arrays['timestamps']
    shot = meta['shot_id']; blocked = []; evidence = []
    by_id = {r['id']: r for r in rules['rules']}
    m = serve_metrics(times, pose)
    if m is None:
        return feedback(shot, by_id['retry_capture'], {}, None, ['load_event_not_found'], evidence, rules, None,
                        rating=rating_cfg and not_rated('retry_capture', rating_cfg))
    q = quality(times, conf, m['load_frame'], GATES['min_joint_score'])
    if not q['at_event_pass'] or q['longest_passing_run_frames'] < GATES['min_consecutive_frames']:
        return feedback(shot, by_id['retry_capture'], {}, None, ['low_joint_confidence'], evidence, rules, None,
                        rating=rating_cfg and not_rated('retry_capture', rating_cfg))
    at_load = smooth(times, pose)[m['load_frame']]
    yaw = (np.sign(at_load[11, 0] - at_load[12, 0]) or 1.0) * estimate_yaw(hip_width_ratio(at_load), ref['hip_width_over_trunk_full'])
    group = {'1': 'first_serve', '2': 'second_serve'}.get(serve_type, 'all')
    row = min(ref['table'][group], key=lambda r: abs(r['yaw_deg'] - yaw))
    metrics = m['values']; evidence = [f'{shot}:{k}' for k, v in metrics.items() if v is not None]
    # Reference eligibility (PRD gates). Validation records do not exist yet, so strict mode always blocks.
    if meta['handedness'] != ref['handedness']: blocked.append('handedness_unknown_or_mismatch')
    if meta['features']['representation'] != ref['representation']: blocked.append('representation_mismatch')
    if abs(yaw) > GATES['max_view_yaw_deg']: blocked.append('view_outside_supported_band')
    if ref['validation']['status'] != 'validated' and not allow_unvalidated_reference: blocked.append('reference_unvalidated')
    reference_ok = not blocked
    if reference_ok: evidence.append(f"{ref['reference_id']}:{group}@yaw{row['yaw_deg']:+d}")
    cue, secondary, praise = select(metrics, row, rules, reference_ok)
    context = {'estimated_view_yaw_deg': round(yaw, 1), 'reference_yaw_deg': row['yaw_deg'], 'reference_group': group,
               'reference_n': row['front_knee_at_load']['n'] if row['front_knee_at_load'] else 0}
    rating = None
    if rating_cfg:  # Djokovic-relative, so it follows the same reference gates as the cues
        rating = (rate_with_view_sensitivity(metrics, ref['table'][group], yaw, rating_cfg) if reference_ok
                  else not_rated('reference_blocked:' + ','.join(blocked), rating_cfg))
    fb = feedback(shot, cue, metrics, row if reference_ok else None, blocked, evidence, rules, praise, context,
                  allow_unvalidated_reference, rating=rating, rating_cfg=rating_cfg)
    fb['secondary_findings'] = secondary; fb['not_measured'] = (rating_cfg or {}).get('not_measured', {})
    return fb

def select(metrics, row, rules, reference_ok):
    """Priority-ordered rule match: (spoken cue, secondary findings, praise or None)."""
    ordered = sorted(rules['rules'], key=lambda r: (r['priority'], r['id']))
    matches = [r for r in ordered if r['kind'] == 'cue' and (reference_ok or r['mode'] != 'reference') and r['mode'] != 'retry'
               and evaluate(r, metrics, row if r['mode'] == 'reference' else None)]
    cue = matches[0]  # one spoken cue; other matching reference findings are kept for the record, not spoken
    secondary = [{'rule_id': r['id'], 'observation': fill(r['observation'], metrics, row), 'suggestion': fill(r['suggestion'], metrics, row),
                  'drill': r['drill']} for r in matches[1:] if r['mode'] == 'reference']
    praise = next((r for r in ordered if r['kind'] == 'praise' and reference_ok and evaluate(r, metrics, row)), None)
    return cue, secondary, praise

def feedback(shot, cue, metrics, row, blocked, evidence, rules, praise, context=None, demo=False, rating=None, rating_cfg=None):
    score = rating and rating.get('score')
    spoken_score = rating_cfg['speech_template'].format(score=score) if score is not None and rating_cfg and rating_cfg.get('speak') else None
    speech = ' '.join(s for s in [spoken_score, praise and praise['canonical_speech'], fill(cue['canonical_speech'], metrics, row)] if s)
    # Only the player's own measurements (and their score) may be spoken; reference values must not become spoken targets.
    numbers = sorted({round(v) for k, v in metrics.items() if v is not None and k.endswith('_at_load')} | ({score} if score is not None else set()))
    return {
        'shot_id': shot, 'mode': cue['mode'], 'rule_id': cue['id'], 'praise_rule_id': praise and praise['id'],
        'rules_version': rules['version'], 'rules_status': rules['status'], 'evidence_ids': evidence,
        'observation': fill(cue['observation'], metrics, row), 'praise': praise and praise['observation'],
        'suggestion': fill(cue['suggestion'], metrics, row), 'drill': cue['drill'],
        'canonical_text': speech, 'praise_speech': praise and praise['canonical_speech'],
        'cue_speech': fill(cue['canonical_speech'], metrics, row) if cue['mode'] != 'observation' else None, 'speech_codes': [c for c in [praise and praise['speech_code'], cue['speech_code']] if c],
        'allowed_numbers': numbers, 'max_words': rules['max_speech_words'], 'metrics': metrics, 'context': context,
        'reference_blocked_reasons': blocked, 'rating': rating,
        'uncertainty': ('UNVALIDATED DEMO: reference comparison enabled without validation records; single 2D camera; '
                        'coaching hypothesis, not a verified technique fault.') if demo and cue['mode'] == 'reference'
                       else 'Single 2D camera; descriptive only.'}

class FeedbackEngine:
    """Composable analyzer: engine(packet_path) -> Feedback dict. Holds reference, rules, rating and gate options."""

    def __init__(self, reference, rules, serve_type='unknown', allow_unvalidated_reference=False, rating=None):
        self.reference, self.rules, self.rating = Path(reference), Path(rules), rating
        self.serve_type, self.allow = serve_type, allow_unvalidated_reference
        for path in (self.reference, self.rules):
            if not path.exists(): raise FileNotFoundError(path)

    def __call__(self, packet_path):
        return decide(packet_path, self.reference, self.rules, self.serve_type, self.allow, self.rating)

def qwen_request(fb, model):
    payload = {'task': 'rewrite_for_speech', 'max_words': fb['max_words'], 'player_handedness': 'right',
               'score': (fb.get('rating') or {}).get('score'), 'praise': fb['praise'], 'observation': fb['observation'], 'cue': fb['suggestion'],
               'allowed_numbers': fb['allowed_numbers'], 'approved_example': fb['canonical_text']}
    return {'model': model, 'temperature': 0.2, 'max_tokens': 80, 'response_format': {'type': 'json_object'},
            'messages': [{'role': 'system', 'content': SYSTEM_PROMPT.format(max_words=fb['max_words'])},
                         {'role': 'user', 'content': json.dumps(payload, indent=1)}]}

def coach_request(fb, model, version='v3'):
    """Coach-voice request: only praise, the approved cue and the score reach the model; no angles or reference values."""
    prompt, examples = COACH_PROMPTS[version]
    score = (fb.get('rating') or {}).get('score')
    note = '\n'.join(line for line in [score is not None and f'Score: {score}', fb.get('praise_speech') and f"Praise: {fb['praise_speech']}",
                                       f"Cue: {fb.get('cue_speech') or 'none'}"] if line)
    shots = [m for q, a in examples for m in ({'role': 'user', 'content': q}, {'role': 'assistant', 'content': a})]
    return {'model': model, 'temperature': 0.2, 'max_tokens': 80,
            'messages': [{'role': 'system', 'content': prompt.format(max_words=fb['max_words'])}, *shots,
                         {'role': 'user', 'content': note}]}

def validate(fb, reply_text, coach=False):
    """Accept Qwen's speech only if it is short, uses allowed numbers, and avoids banned claims; else canonical text."""
    reasons = []
    try:
        text = json.loads(reply_text)['speech'].strip()
    except (ValueError, KeyError, TypeError, AttributeError):
        match = re.search(r'"speech"\s*:\s*"([^"]+)"', reply_text or ''); text = match.group(1).strip() if match else (reply_text or '').strip()
        reasons.append('reply_not_strict_json')
    if not text: reasons.append('empty')
    if len(text.split()) > fb['max_words']: reasons.append('too_long')
    allowed = {(fb.get('rating') or {}).get('score')} if coach else set(fb['allowed_numbers'])  # v2 speaks no measurements
    extra = {int(float(n)) for n in re.findall(r'\d+(?:\.\d+)?', text)} - allowed
    if extra: reasons.append(f'unapproved_numbers:{sorted(extra)}')
    if BANNED.search(text): reasons.append('banned_claim')
    if coach and PRO_NAMES.search(text): reasons.append('mentions_pro')
    if coach and not fb.get('praise') and PRAISE_WORDS.search(text): reasons.append('praise_not_in_note')
    if re.search(r'\bscore', text, re.I) and (fb.get('rating') or {}).get('score') is None: reasons.append('score_without_rating')
    approved = ' '.join(x for x in (fb['praise'], fb['observation'], fb['suggestion'], fb['canonical_text'], fb.get('cue_speech')) if x).lower()
    new_topics = [w for w in TOPIC_WORDS if re.search(rf'\b{w}', text, re.I) and not re.search(rf'\b{w}', approved)]
    if new_topics: reasons.append(f'unapproved_topics:{new_topics}')
    hard = [r for r in reasons if r != 'reply_not_strict_json']
    return {'accepted': not hard, 'speech': text if not hard else fb['canonical_text'], 'source': 'qwen' if not hard else 'canonical_fallback',
            'qwen_text': text, 'reasons': reasons}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('decide'); d.add_argument('packet', type=Path); d.add_argument('--out', type=Path, required=True)
    d.add_argument('--reference', type=Path, default=ROOT / 'reference/projected2d/board_reference.json')
    d.add_argument('--rules', type=Path, default=ROOT / 'coaching/rules.json')
    d.add_argument('--serve-type', choices=['1', '2', 'unknown'], default='unknown')
    d.add_argument('--allow-unvalidated-reference', action='store_true', help='Demo only: enable Djokovic-relative rules before validation')
    d.add_argument('--model', default='gemma4:e2b')
    v = sub.add_parser('validate'); v.add_argument('feedback', type=Path); v.add_argument('reply', type=Path, help="File with Qwen's reply text, or - for stdin")
    a = p.parse_args()
    if a.cmd == 'decide':
        fb = decide(a.packet, a.reference, a.rules, a.serve_type, a.allow_unvalidated_reference)
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / 'feedback.json').write_text(json.dumps(fb, indent=2) + '\n')
        (a.out / 'phrase_request.json').write_text(json.dumps(coach_request(fb, a.model), indent=2) + '\n')
        print(json.dumps({k: fb[k] for k in ('mode', 'rule_id', 'praise_rule_id', 'canonical_text', 'reference_blocked_reasons')}, indent=1))
    else:
        fb = json.loads(a.feedback.read_text()); reply = sys.stdin.read() if str(a.reply) == '-' else a.reply.read_text()
        print(json.dumps(validate(fb, reply, coach=True), indent=1))

if __name__ == '__main__':
    main()
