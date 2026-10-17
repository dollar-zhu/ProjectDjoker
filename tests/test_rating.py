import json
import unittest
from pathlib import Path
from coaching.rating import metric_score, rate, rate_with_view_sensitivity
from coaching.board_feedback import decide, qwen_request, validate

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'coaching/rating.json').read_text())
BOARD_REF = ROOT / 'reference/projected2d/board_reference.json'
RULES = ROOT / 'coaching/rules.json'
GOLDEN = ROOT / 'local/golden/dms/golden.json'  # private fixture, not in git
BAND = {'p10': 100.0, 'p25': 102.0, 'median': 105.0, 'p75': 108.0, 'p90': 110.0, 'n': 50}

class MetricScore(unittest.TestCase):
    def test_inside_band_is_full_score(self):
        for v in (100.0, 105.0, 110.0): self.assertEqual(metric_score(v, BAND, 25.0)[0], 100.0)

    def test_linear_decay_on_both_sides_and_floor(self):
        self.assertAlmostEqual(metric_score(122.5, BAND, 25.0)[0], 50.0)
        self.assertAlmostEqual(metric_score(87.5, BAND, 25.0)[0], 50.0)
        self.assertEqual(metric_score(200.0, BAND, 25.0)[0], 0.0)

class Rate(unittest.TestCase):
    row = {name: BAND for name in CONFIG['metrics']}

    def test_all_inside_scores_100_with_full_coverage(self):
        r = rate({name: 105.0 for name in CONFIG['metrics']}, self.row, CONFIG)
        self.assertEqual(r['score'], 100); self.assertEqual(r['coverage'], 1.0)

    def test_missing_metrics_renormalize_until_coverage_gate(self):
        names = list(CONFIG['metrics'])
        partial = {n: 105.0 for n in names[:5]}  # knees, bend/push-up timing, drive = 0.60 of the weight
        self.assertEqual(rate(partial, self.row, CONFIG)['score'], 100)
        sparse = {names[0]: 105.0}  # 0.17 of the weight < min_coverage
        r = rate(sparse, self.row, CONFIG)
        self.assertIsNone(r['score']); self.assertEqual(r['reason'], 'insufficient_metric_coverage')

    def test_p25_p75_band_used_for_arm_metrics(self):
        self.assertEqual(CONFIG['metrics']['arm_fold_lead']['band'], 'p25_p75')
        r = rate({'arm_fold_lead': 109.0, **{n: 105.0 for n in CONFIG['metrics'] if n != 'arm_fold_lead'}}, self.row, CONFIG)
        item = next(i for i in r['items'] if i['metric'] == 'arm_fold_lead')
        self.assertEqual(item['band'], [102.0, 108.0]); self.assertEqual(item['direction'], 'above'); self.assertLess(item['score'], 100)

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(m['weight'] for m in CONFIG['metrics'].values()), 1.0)

    def test_view_sensitivity_range_brackets_score(self):
        table = [dict({n: dict(BAND, p10=100 + d, p25=102 + d, p75=108 + d, p90=110 + d) for n in CONFIG['metrics']}, yaw_deg=y)
                 for y, d in ((-10, -5), (0, 0), (10, 5))]
        r = rate_with_view_sensitivity({n: 112.0 for n in CONFIG['metrics']}, table, 0, CONFIG)
        lo, hi = r['score_range_view_uncertainty']
        self.assertLessEqual(lo, r['score']); self.assertGreaterEqual(hi, r['score'])

@unittest.skipUnless(BOARD_REF.exists() and GOLDEN.exists(), 'needs reference table and private golden fixtures (scripts/make_golden.py)')
class Serve1(unittest.TestCase):
    def test_demo_score_is_deterministic_and_spoken_within_limit(self):
        a = decide(GOLDEN, BOARD_REF, RULES, allow_unvalidated_reference=True)
        b = decide(GOLDEN, BOARD_REF, RULES, allow_unvalidated_reference=True)
        self.assertEqual(a['rating'], b['rating']); self.assertEqual(a['rating']['score'], 81)
        self.assertTrue(a['canonical_text'].startswith('Score 81.')); self.assertLessEqual(len(a['canonical_text'].split()), 25)
        self.assertIn(81, a['allowed_numbers'])
        self.assertEqual(json.loads(qwen_request(a, 'q')['messages'][1]['content'])['score'], 81)
        self.assertTrue(validate(a, json.dumps({'speech': 'Score 81. Great leg drive, now sink into your front knee.'}))['accepted'])
        self.assertFalse(validate(a, json.dumps({'speech': 'Score 95. Sink into your front knee.'}))['accepted'])

    def test_arm_findings_recorded_but_one_cue_spoken(self):
        fb = decide(GOLDEN, BOARD_REF, RULES, allow_unvalidated_reference=True)
        ids = [x['rule_id'] for x in fb['secondary_findings']]
        self.assertEqual(fb['rule_id'], 'serve_knee_loading_front_leg')
        self.assertIn('serve_trophy_elbow_low', ids); self.assertIn('serve_arm_early', ids)
        self.assertNotIn('elbow', fb['canonical_text'].lower())
        self.assertIn('pronation', fb['not_measured'])

    def test_strict_mode_withholds_score(self):
        fb = decide(GOLDEN, BOARD_REF, RULES)
        self.assertIsNone(fb['rating']['score']); self.assertIn('reference_unvalidated', fb['rating']['reason'])
        self.assertNotIn('Score', fb['canonical_text'])
        r = validate(fb, json.dumps({'speech': 'Score 80. Serve recorded.'}))
        self.assertFalse(r['accepted']); self.assertIn('score_without_rating', r['reasons'])

if __name__ == '__main__':
    unittest.main()
