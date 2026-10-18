import unittest
import commentary

class StageAnalysisTests(unittest.TestCase):
    def stage(self,id,measurements):
        return {'id':id,'status':'estimated','evidence':[{'observation':'The hitting arm lowers after reach.','measurements':measurements}]}
    def test_visible_extension_supports_a_rhythm_practice_not_a_bend_correction(self):
        r=commentary.fallback_plan({'stages':[self.stage('acceleration',{'mean_knee_change_deg':30})]})
        self.assertEqual(r['focus_id'],'rhythm');self.assertIn('five',r['drill'])
    def test_missing_or_negative_leg_evidence_does_not_claim_extension(self):
        for v in [None,-15,float('nan')]:
            r=commentary.fallback_plan({'stages':[self.stage('acceleration',{'mean_knee_change_deg':v})]})
            self.assertEqual(r['focus_id'],'recapture')
    def test_visible_elbow_recovery_does_not_claim_ball_contact_or_balance(self):
        r=commentary.fallback_plan({'stages':[self.stage('follow_through',{})]})
        self.assertEqual(r['focus_id'],'recovery');self.assertIn('does not establish',r['limitation'])
    def test_no_stage_evidence_requests_a_clearer_recording(self):
        r=commentary.fallback_plan({'stages':[]});self.assertEqual(r['mode'],'recapture');self.assertEqual(r['evidence_times'],[])
