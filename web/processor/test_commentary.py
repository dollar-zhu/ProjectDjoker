import unittest
from commentary import prepare_evidence,generate

class CommentaryTests(unittest.TestCase):
    def evidence(self):return {'player':'Novak Djokovic','time':1.6,'userLeft':140,'userRight':145,'referenceLeft':100,'referenceRight':110}
    def test_comparison_preserves_measurements_without_turning_similarity_into_quality(self):
        e=prepare_evidence(self.evidence());self.assertEqual(e['direction'],'review');self.assertEqual(e['time'],1.6)
        self.assertEqual(e['userLeft'],140);self.assertIn('does not establish',e['observation'])
    def test_invalid_evidence_rejected(self):
        for value in [float('nan'),True,200]:
            x=self.evidence();x['userLeft']=value
            with self.assertRaises(ValueError):prepare_evidence(x)
    def test_comparison_does_not_claim_model_inference(self):
        x=generate(self.evidence());self.assertEqual(x['model_status'],'not_requested');self.assertNotIn('Gemma',x['source'])
