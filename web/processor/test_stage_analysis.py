import unittest
import commentary


class StageAnalysisTests(unittest.TestCase):
    def stages(self):
        return [{'id':'loading','label':'Loading','status':'estimated','time':1.2,
                 'evidence':[{'id':'loading','observation':'Knees visibly bend.','cue':'Replay the knee bend.','measurements':{'left_knee_deg':130}}]},
                {'id':'finish','label':'Finish','status':'unavailable','time':None,'evidence':[]}]

    def test_only_observed_stages_are_model_choices(self):
        self.assertTrue(hasattr(commentary,'stage_candidates'))
        candidates=commentary.stage_candidates(self.stages())
        self.assertEqual([c['id'] for c in candidates],['loading'])
        self.assertEqual(candidates[0]['time'],1.2)

    def test_model_can_select_evidence_but_cannot_create_a_diagnosis(self):
        self.assertTrue(hasattr(commentary,'parse_stage_reply'))
        candidates=[{'id':'loading','observation':'Knees visibly bend.','cue':'Replay the knee bend.'}]
        self.assertEqual(commentary.parse_stage_reply('{"focus_id":"loading"}',candidates),'loading')
        self.assertIsNone(commentary.parse_stage_reply('{"focus_id":"finish"}',candidates))
        self.assertIsNone(commentary.parse_stage_reply('{"focus_id":"loading","diagnosis":"bad shoulder"}',candidates))
        self.assertIsNone(commentary.parse_stage_reply('You need to bend more.',candidates))

    def test_no_evidence_has_an_explicit_unavailable_result(self):
        self.assertTrue(hasattr(commentary,'analyse_stages'))
        r=commentary.analyse_stages([])
        self.assertEqual(r['model_status'],'no_evidence');self.assertIsNone(r['focus_id'])

    def test_unavailable_board_preserves_measured_feedback(self):
        from unittest.mock import patch
        import tempfile,os
        self.assertTrue(hasattr(commentary,'analyse_stages'))
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'DJOKER_DATA_DIR':d+'/jobs'}),patch.object(commentary.subprocess,'run',side_effect=OSError('no board')):
            r=commentary.analyse_stages(self.stages())
        self.assertEqual(r['model_status'],'unavailable');self.assertEqual(r['focus_id'],'loading')
        self.assertEqual(r['observation'],'Knees visibly bend.')
