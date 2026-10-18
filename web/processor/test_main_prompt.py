import json
import unittest

import commentary
from coaching.board_feedback import coach_request


class MainPromptTests(unittest.TestCase):
    def candidates(self):
        return commentary.coaching_candidates({'stages':[
            {'id':'acceleration','status':'estimated','start':1.2,'end':1.8,
             'evidence':[{'measurements':{'mean_knee_change_deg':32}}]},
            {'id':'follow_through','status':'estimated','start':1.8,'end':2.5,
             'evidence':[{'measurements':{}}]},
        ]})

    def test_review_uses_main_v3_messages_for_one_approved_cue(self):
        candidates=self.candidates()
        request=commentary.coaching_request(candidates)
        expected=coach_request({'max_words':55,'cue_speech':candidates[0]['cue']},commentary.MODEL)
        self.assertEqual(request['messages'],expected['messages'])
        self.assertEqual(request['options']['temperature'],expected['temperature'])
        self.assertEqual(request['options']['num_predict'],expected['max_tokens'])
        self.assertNotIn('32',request['messages'][-1]['content'])
        self.assertNotIn(candidates[1]['cue'],request['messages'][-1]['content'])

    def test_speech_response_preserves_review_card_and_evidence_links(self):
        candidates=self.candidates()
        speech='Next one, keep one smooth bend-and-rise rhythm.'
        result=commentary.parse_coach_reply(json.dumps({'speech':speech}),candidates)
        self.assertIsNotNone(result)
        self.assertEqual(result['cue'],speech)
        for key in ['focus_id','stage_id','drill','success_check','evidence_times']:
            self.assertEqual(result[key],candidates[0][key])
        self.assertEqual(result['rationale'],candidates[0]['purpose'])

    def test_old_prompt_schema_and_main_validator_rejections_fall_back(self):
        candidates=self.candidates()
        for reply in [{'focus_id':'rhythm','cue':candidates[0]['cue'],'why':'A generated explanation.'},
                      {'speech':'Great job! Keep one smooth bend-and-rise rhythm.'},
                      {'speech':'Bend your knees 90 degrees like Djokovic.'},
                      {'speech':'Change your wrist position.'}]:
            self.assertIsNone(commentary.parse_coach_reply(json.dumps(reply),candidates))
