"""Phrasers turn a Feedback decision into the sentence that is spoken. phrase(feedback) -> dict.

CanonicalPhraser speaks the approved text. QwenPhraser asks an OpenAI-compatible endpoint (Gemma 4 E2B by default)
to add brief praise and linking words around the approved cue (prompt v3), validates the reply, and falls back to the
canonical text on timeout, error or any rule violation.
"""
import json
import time
import urllib.request
from .board_feedback import coach_request, validate

class CanonicalPhraser:
    name = 'canonical'

    def phrase(self, feedback):
        return {'speech': feedback['canonical_text'], 'source': 'canonical', 'latency_ms': 0.0}

class QwenPhraser:
    name = 'qwen'

    def __init__(self, url, model, timeout_s=1.0):
        self.url, self.model, self.timeout_s = url, model, timeout_s

    def phrase(self, feedback):
        if feedback.get('suggestion') is None:  # retry/observation: nothing approved to rephrase
            return dict(CanonicalPhraser().phrase(feedback), reasons=['nothing_to_rephrase'])
        t0 = time.perf_counter()
        try:
            body = json.dumps(coach_request(feedback, self.model)).encode()
            req = urllib.request.Request(self.url, body, {'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                reply = json.loads(resp.read())['choices'][0]['message']['content']
            result = validate(feedback, reply, coach=True)
        except Exception as exc:  # noqa: BLE001 - timeout or server error -> canonical text
            result = {'accepted': False, 'speech': feedback['canonical_text'], 'source': 'canonical_fallback',
                      'reasons': [f'qwen_error:{type(exc).__name__}']}
        result['latency_ms'] = (time.perf_counter() - t0) * 1000
        return result

def make_phraser(cfg):
    cfg = cfg or {}
    if cfg.get('backend', 'canonical') == 'qwen':
        return QwenPhraser(cfg['url'], cfg.get('model', 'qwen'), float(cfg.get('timeout_s', 1.0)))
    return CanonicalPhraser()
