"""Compare spoken-feedback prompts across small models served by Ollama.

    .venv/bin/python -m coaching.evals.run_eval --models gemma4:e2b gemma3:1b --prompts v1 v2 --judge gemma4:31b

v1 is the current device prompt (`qwen_request`), v2 the coach prompt (`coach_request`). Each reply is checked by the
production validator for its prompt version plus shared quality checks, and optionally scored by a larger local judge.
Results go to local/evals/<timestamp>/ (git-ignored). Mac Ollama quantization differs from the board's ExecuTorch
build, so treat this as a prompt comparison, not a device benchmark.
"""
import argparse
import json
import re
import statistics
import time
import urllib.request
from pathlib import Path
from coaching.board_feedback import ROOT, PRAISE_WORDS, PRO_NAMES, coach_request, qwen_request, validate
from coaching.evals.cases import build

OLLAMA = 'http://localhost:11434/api/chat'
REQUESTS = {'v1': qwen_request, 'v2': lambda fb, m: coach_request(fb, m, 'v2'), 'v3': lambda fb, m: coach_request(fb, m, 'v3')}
# The spoken text must still carry the approved cue: one of these stems per rule.
CUE_WORDS = {'serve_knee_loading_front_leg': ['front'], 'serve_knee_loading_shallow': ['bend', 'sink', 'lower', 'deep', 'knee'],
             'serve_trophy_elbow_low': ['elbow'], 'serve_arm_early': ['fold', 'arm'], 'serve_load_tempo': ['slow', 'smooth', 'sink', 'gradual'],
             'retry_capture': ['view', 'see', 'frame', 'camera']}
JUDGE_PROMPT = """You are an experienced tennis coach reviewing what a coaching device said to a player right after a serve.
The device was given this approved note (it may only use these facts):
{note}

The device said: "{speech}"

Score 1-5 on each:
- coach_like: sounds like a good human coach talking to a player (natural, warm, not robotic, no jargon or numbers dumping)
- actionable: the player knows exactly one thing to feel or do on the next serve (score 3 if the note has no cue and it simply encourages)
- faithful: says only what the note supports; no new advice, body parts, numbers or comparisons
Reply with JSON only: {{"coach_like": n, "actionable": n, "faithful": n, "comment": "one short sentence"}}"""


def chat(model, messages, temperature, max_tokens, json_mode=False):
    body = {'model': model, 'messages': messages, 'stream': False,
            'options': {'temperature': temperature, 'num_predict': max_tokens, 'seed': 7}}
    if model.startswith(('gemma4', 'qwen3')): body['think'] = False
    if json_mode: body['format'] = 'json'
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {'Content-Type': 'application/json'})
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    return out['message']['content'], time.monotonic() - start


def speech_of(reply):
    text = re.sub(r'^```(?:json)?|```$', '', reply.strip(), flags=re.M).strip()
    try: return json.loads(text)['speech'].strip(), True
    except (ValueError, KeyError, TypeError, AttributeError):
        m = re.search(r'"speech"\s*:\s*"([^"]+)"', reply); return (m.group(1).strip() if m else reply.strip()), False


def checks(fb, speech):
    score = (fb.get('rating') or {}).get('score')
    numbers = {int(float(n)) for n in re.findall(r'\d+(?:\.\d+)?', speech)} - ({score} if score is not None else set())
    words = CUE_WORDS.get(fb['rule_id'])
    return {'within_length': len(speech.split()) <= fb['max_words'], 'no_measurements': not numbers and 'degree' not in speech.lower(),
            'no_pro_comparison': not PRO_NAMES.search(speech), 'no_invented_praise': bool(fb.get('praise')) or not PRAISE_WORDS.search(speech),
            'keeps_cue': True if words is None else any(w in speech.lower() for w in words)}


def note(fb):
    return '\n'.join(f'{k}: {v}' for k, v in [('score', (fb.get('rating') or {}).get('score')), ('praise', fb.get('praise_speech')),
                                              ('cue', fb.get('cue_speech') or 'none (observation only)'), ('drill', fb.get('drill'))] if v is not None)


def judge(model, fb, speech):
    reply, _ = chat(model, [{'role': 'user', 'content': JUDGE_PROMPT.format(note=note(fb), speech=speech)}], 0, 200, json_mode=True)
    try:
        v = json.loads(reply); return {k: v[k] for k in ('coach_like', 'actionable', 'faithful', 'comment')}
    except (ValueError, KeyError): return None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--models', nargs='+', default=['gemma4:e2b', 'gemma3:1b'])
    p.add_argument('--prompts', nargs='+', default=['v1', 'v3'], choices=sorted(REQUESTS))
    p.add_argument('--samples', type=int, default=3, help='extra temperature-0.7 samples per case for robustness checks')
    p.add_argument('--judge', default=None, help='Ollama model that scores the temperature-0 replies')
    p.add_argument('--out', type=Path, default=ROOT / 'local/evals' / time.strftime('%Y%m%d-%H%M%S'))
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True); cases = build(); rows = []
    (a.out / 'cases.json').write_text(json.dumps(cases, indent=1, default=str))
    for model in a.models:
        for version in a.prompts:
            for case in cases:
                fb = case['feedback']; req = REQUESTS[version](fb, model)
                if fb.get('suggestion') is None:  # as on the device (phraser.py): no cue, no model call; canonical text is spoken
                    rows.append({'model': model, 'prompt': version, 'case': case['id'], 'sample': 0, 'model_called': False,
                                 'rule_id': fb['rule_id'], 'speech': fb['canonical_text'], 'heard': fb['canonical_text'],
                                 'accepted': True, 'reject_reasons': [], 'parsed_json': True, 'latency_s': 0.0, **checks(fb, fb['canonical_text'])})
                    continue
                for sample in range(1 + a.samples):
                    temperature = 0 if sample == 0 else 0.7
                    reply, latency = chat(model, req['messages'], temperature, 120)
                    speech, parsed = speech_of(reply)
                    verdict = validate(fb, reply, coach=version == 'v2')
                    row = {'model': model, 'prompt': version, 'case': case['id'], 'sample': sample, 'temperature': temperature, 'model_called': True,
                           'rule_id': fb['rule_id'], 'speech': speech, 'parsed_json': parsed, 'latency_s': round(latency, 2),
                           'accepted': verdict['accepted'], 'reject_reasons': verdict['reasons'], 'heard': verdict['speech'],
                           **checks(fb, speech)}
                    if sample == 0 and a.judge: row['judge'] = judge(a.judge, fb, speech)
                    rows.append(row); print(f"{model:12s} {version} {case['id']:28s} s{sample} {'OK ' if row['accepted'] else 'REJ'} {speech[:90]}")
    with (a.out / 'results.jsonl').open('w') as f:
        for r in rows: f.write(json.dumps(r) + '\n')
    summary = summarize(rows); (a.out / 'summary.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1)); print('results:', a.out)


def summarize(rows):
    out = {}
    for key in sorted({(r['model'], r['prompt']) for r in rows}):
        group = [r for r in rows if (r['model'], r['prompt']) == key and r['model_called']]; judged = [r['judge'] for r in group if r.get('judge')]
        rate = lambda k: round(sum(bool(r[k]) for r in group) / len(group), 3)
        out[f'{key[0]} {key[1]}'] = {
            'n': len(group), **{k: rate(k) for k in ('accepted', 'parsed_json', 'within_length', 'no_measurements', 'no_pro_comparison', 'no_invented_praise', 'keeps_cue')},
            'all_checks': round(sum(r['accepted'] and r['no_measurements'] and r['no_pro_comparison'] and r['no_invented_praise'] and r['keeps_cue'] for r in group) / len(group), 3),
            'median_latency_s': statistics.median(r['latency_s'] for r in group),
            **({f'judge_{k}': round(statistics.mean(j[k] for j in judged), 2) for k in ('coach_like', 'actionable', 'faithful')} if judged else {})}
    return out


if __name__ == '__main__':
    main()
