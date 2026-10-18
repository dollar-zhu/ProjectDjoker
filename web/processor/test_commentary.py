import unittest
from commentary import prepare_evidence,validate_reply
class CommentaryTests(unittest.TestCase):
    def evidence(self): return {'player':'Novak Djokovic','time':1.6,'userLeft':140,'userRight':145,'referenceLeft':100,'referenceRight':110}
    def test_measured_direction_and_timestamp_are_preserved(self):
        e=prepare_evidence(self.evidence());self.assertEqual(e['direction'],'more_bend');self.assertEqual(e['time'],1.6)
        self.assertTrue(validate_reply('Try a slightly deeper knee bend during loading in a relaxed shadow serve.',e))
        self.assertFalse(validate_reply('Straighten your knees during loading.',e))
        self.assertFalse(validate_reply('Bend your knees 40 degrees more to avoid injury and serve faster.',e))
    def test_mixed_directions_do_not_prescribe_more_bend(self):
        x=self.evidence();x['userRight']=80;self.assertEqual(prepare_evidence(x)['direction'],'review')
    def test_one_straighter_knee_with_other_matching_gets_specific_focus(self):
        x=self.evidence();x['referenceRight']=145
        e=prepare_evidence(x);self.assertEqual(e['direction'],'more_bend');self.assertIn('left knee',e['observation'])
    def test_extra_weight_transfer_is_rejected(self):
        e=prepare_evidence(self.evidence())
        self.assertFalse(validate_reply('Shift your weight forward for a deeper knee bend during loading.',e))
    def test_invalid_evidence_rejected(self):
        x=self.evidence();x['userLeft']=float('nan')
        with self.assertRaises(ValueError): prepare_evidence(x)
