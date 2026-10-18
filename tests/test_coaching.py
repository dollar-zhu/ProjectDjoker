import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from coaching.board_feedback import decide, validate, qwen_request
from tests.test_compare2d import Comparison, REFERENCE

ROOT = Path(__file__).resolve().parents[1]
BOARD_REF = ROOT / 'reference/projected2d/board_reference.json'
RULES = ROOT / 'coaching/rules.json'

@unittest.skipUnless(BOARD_REF.exists() and REFERENCE.exists(), 'run python -m compare2d.reference first')
class Decide(unittest.TestCase):
    def packet(self, tmp, yaw=20, confidence=0.9, handedness='right'):
        helper = Comparison(); pose, _ = helper.reference_serve_2d(yaw)
        path = helper.packet(tmp, pose, handedness=handedness)
        if confidence != 0.9:
            c = np.load(path.parent / 'synthetic_confidence.npy'); c[:] = confidence; np.save(path.parent / 'synthetic_confidence.npy', c)
        return path

    def test_strict_mode_never_uses_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            fb = decide(self.packet(tmp), BOARD_REF, RULES)
        self.assertEqual(fb['mode'], 'observation'); self.assertIn('reference_unvalidated', fb['reference_blocked_reasons'])
        self.assertNotIn('Djokovic', fb['canonical_text']); self.assertIsNone(fb['praise'])

    def test_demo_mode_is_deterministic_and_reference_like_serve_gets_no_correction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.packet(tmp)  # one of Djokovic's own serves, projected to 2D
            a = decide(path, BOARD_REF, RULES, allow_unvalidated_reference=True)
            b = decide(path, BOARD_REF, RULES, allow_unvalidated_reference=True)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(a['rule_id'], 'serve_observation')
        self.assertEqual(len([c for c in a['speech_codes'] if c != 'SERVE_DRIVE_GOOD']), 1)
        self.assertLessEqual(len(a['canonical_text'].split()), 25)

    @unittest.skipUnless((ROOT / 'runs/dev/serve1/dms/serve1.json').exists(), 'Serve1 packet not generated')
    def test_serve1_demo_selects_front_leg_cue(self):
        fb = decide(ROOT / 'runs/dev/serve1/dms/serve1.json', BOARD_REF, RULES, allow_unvalidated_reference=True)
        self.assertEqual(fb['rule_id'], 'serve_knee_loading_front_leg'); self.assertEqual(fb['praise_rule_id'], 'serve_leg_drive_positive')
        self.assertIn('UNVALIDATED', fb['uncertainty'])

    def test_unknown_handedness_blocks_reference_even_in_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            fb = decide(self.packet(tmp, handedness='unknown'), BOARD_REF, RULES, allow_unvalidated_reference=True)
        self.assertEqual(fb['mode'], 'observation'); self.assertIn('handedness_unknown_or_mismatch', fb['reference_blocked_reasons'])

    def test_low_confidence_asks_for_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            fb = decide(self.packet(tmp, confidence=0.2), BOARD_REF, RULES, allow_unvalidated_reference=True)
        self.assertEqual(fb['rule_id'], 'retry_capture'); self.assertIsNone(fb['drill'])

class Validate(unittest.TestCase):
    fb = {'max_words': 25, 'allowed_numbers': [105, 115], 'praise': "Your leg drive was as quick as Djokovic's.",
          'observation': 'At your deepest bend your front knee was 115 degrees and your back knee 105.',
          'suggestion': 'Sink into your front knee and keep the back leg quieter.',
          'canonical_text': 'Good leg drive. Sink into your front knee, not your back knee.'}

    def check(self, speech):
        return validate(self.fb, json.dumps({'speech': speech}))

    def test_accepts_faithful_rephrase(self):
        r = self.check('Great leg drive! Sink into your front knee and keep that back leg quiet.')
        self.assertTrue(r['accepted']); self.assertEqual(r['source'], 'qwen')

    def test_rejections_fall_back_to_canonical(self):
        for speech, reason in [('Bend your front knee to 103 like Djokovic.', 'unapproved_numbers'),
                               ('Sink into the front knee and toss higher.', 'unapproved_topics'),
                               ('Front knee deeper to avoid injury.', 'banned_claim'),
                               (' '.join(['knee'] * 30), 'too_long')]:
            r = self.check(speech)
            self.assertFalse(r['accepted']); self.assertEqual(r['speech'], self.fb['canonical_text'])
            self.assertTrue(any(x.startswith(reason) for x in r['reasons']), (speech, r['reasons']))

    def test_garbage_reply_falls_back(self):
        r = validate(self.fb, '')
        self.assertFalse(r['accepted']); self.assertEqual(r['speech'], self.fb['canonical_text'])

    def test_request_is_openai_chat_shape(self):
        fb = dict(self.fb, suggestion='Sink into your front knee.')
        req = qwen_request(fb, 'qwen-test')
        self.assertEqual([m['role'] for m in req['messages']], ['system', 'user'])
        self.assertEqual(json.loads(req['messages'][1]['content'])['allowed_numbers'], [105, 115])

if __name__ == '__main__':
    unittest.main()
