import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
import commentary

class CoachTests(unittest.TestCase):
    def result(self):
        return {'stages':[{'id':'acceleration','status':'estimated','start':1.2,'end':1.8,'time':1.8,'evidence':[{'observation':'The knees are 32 degrees straighter.','measurements':{'mean_knee_change_deg':32}}]}]}
    def candidates(self):return commentary.coaching_candidates(self.result())
    def reply(self):return {'speech':'Next one, keep one smooth bend-and-rise rhythm.'}
    def test_player_receives_an_action_drill_and_check_without_joint_angles(self):
        c=self.candidates();r=commentary.parse_coach_reply(json.dumps(self.reply()),c)
        self.assertEqual(r['focus_id'],'rhythm');self.assertIn('five',r['drill']);self.assertTrue(r['success_check'])
        self.assertNotRegex(' '.join(r[k] for k in ['observation','cue','rationale','drill','success_check']),r'\d|°|degrees')
        self.assertEqual(r['evidence_times'],[1.2,1.8])
    def test_missing_leg_tracking_never_becomes_a_leg_fault(self):
        result=self.result();result['stages'][0]['status']='unavailable'
        c=commentary.coaching_candidates(result)
        self.assertEqual([x['focus_id'] for x in c],['recapture'])
        self.assertIsNone(commentary.parse_coach_reply(json.dumps(self.reply()),c))
    def test_rejects_unapproved_topics_numbers_praise_and_extra_fields(self):
        for reply in [{'speech':'Change your grip and wrist position.'},
                      {'speech':'Bend your knees 130 degrees.'},
                      {'speech':'Great work! Keep one smooth bend-and-rise rhythm.'},
                      {'speech':self.reply()['speech'],'extra':'Add a faster swing.'},
                      {'speech':None}]:
            self.assertIsNone(commentary.parse_coach_reply(json.dumps(reply),self.candidates()))
    def test_repeated_video_frames_request_recapture_not_technique_advice(self):
        c=commentary.coaching_candidates(self.result(),{'status':'repeated_frames','duplicate_fraction':.99})
        self.assertEqual([x['focus_id'] for x in c],['recapture']);self.assertIn('repeat',c[0]['observation'])
    def test_recapture_never_uses_a_generated_speech_reply(self):
        c=commentary.coaching_candidates({}, {'status':'repeated_frames'})
        self.assertIsNone(commentary.parse_coach_reply(json.dumps({'speech':c[0]['cue']}),c))
    def test_explanation_remains_the_authored_purpose(self):
        c=self.candidates();r=commentary.parse_coach_reply(json.dumps(self.reply()),c)
        self.assertEqual(r['rationale'],c[0]['purpose'])
    def test_model_cannot_switch_the_selected_focus(self):
        self.assertIsNone(commentary.parse_coach_reply(json.dumps({'speech':self.reply()['speech'],'focus_id':'recovery'}),self.candidates()))
    def test_freeze_detector_distinguishes_paused_video_from_movement(self):
        with tempfile.TemporaryDirectory() as d:
            for moving in [False,True]:
                p=Path(d)/f'{moving}.mp4';v=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*'mp4v'),30,(320,240))
                for i in range(60):
                    im=np.full((240,320,3),120,np.uint8)
                    if moving:cv2.rectangle(im,(i*3,40),(i*3+40,180),(255,255,255),-1)
                    v.write(im)
                v.release();q=commentary.video_quality(p)
                self.assertEqual(q['status'],'usable' if moving else 'repeated_frames')
    def test_board_transport_never_uses_the_macs_ollama(self):
        from subprocess import CompletedProcess
        with patch.object(commentary.subprocess,'run',return_value=CompletedProcess([],0,'{"models":[]}','')) as run:
            commentary.model_request('tags')
        args=run.call_args.args[0]
        self.assertEqual(args[:3],['adb','-s','242692658']);self.assertIn('shell',args)
        self.assertIn('127.0.0.1:11434',args[-1])
    def test_missing_evidence_is_handled_before_calling_gemma(self):
        with patch.object(commentary,'video_quality',return_value={'status':'repeated_frames'}),patch.object(commentary,'model_request') as request:
            r=commentary.analyse_video(Path('/unused'),self.result())
        request.assert_not_called();self.assertEqual(r['model_status'],'insufficient_evidence')
        self.assertEqual(r['focus_id'],'recapture');self.assertNotIn('Gemma',r['source'])
    def test_no_silent_gemma3_or_mac_model_fallback(self):
        with patch.dict(os.environ,{'DJOKER_GEMMA_MODEL':'gemma3:1b'}):
            self.assertEqual(commentary.analyse_video(Path('/unused'),{})['model_status'],'unsupported_model')

class CoachRuntimeTests(unittest.TestCase):
    def test_accepted_board_result_is_cached_but_rejected_reply_can_be_retried(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'DJOKER_DATA_DIR':d+'/jobs','DJOKER_GEMMA_MODEL':'gemma4:e2b'}),patch.object(commentary,'video_quality',return_value={'status':'usable'}):
            p=Path(d)/'video.mp4';p.write_bytes(b'video');outputs=iter(['invalid',json.dumps(CoachTests().reply()),'invalid']);calls=[]
            def request(route,payload=None,timeout=120):
                if route=='tags':return {'models':[{'name':'gemma4:e2b','digest':'test-weights'}]}
                calls.append(payload)
                return {'model':'gemma4:e2b','message':{'content':next(outputs)},'done_reason':'stop'}
            with patch.object(commentary,'model_request',side_effect=request):
                result=CoachTests().result()
                self.assertEqual(commentary.analyse_video(p,result)['model_status'],'reply_rejected')
                r=commentary.analyse_video(p,result)
                self.assertEqual(r['model_status'],'completed');self.assertIn('Ventuno',r['source']);self.assertIn('CPU',r['source']);self.assertFalse(r['cached'])
                self.assertTrue(commentary.analyse_video(p,result)['cached']);self.assertEqual(len(calls),2)
                self.assertNotIn('images',calls[0]['messages'][-1]);self.assertNotIn('degrees',calls[0]['messages'][-1]['content'])
                result['stages'][0]['evidence'][0]['measurements']['mean_knee_change_deg']=-10
                r=commentary.analyse_video(p,result);self.assertFalse(r.get('cached',False))
    def test_offline_retains_useful_practice_with_honest_provenance(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'DJOKER_DATA_DIR':d+'/jobs'}),patch.object(commentary,'video_quality',return_value={'status':'usable'}),patch.object(commentary,'model_request',side_effect=OSError('offline')):
            p=Path(d)/'video.mp4';p.write_bytes(b'x');r=commentary.analyse_video(p,CoachTests().result())
        self.assertEqual(r['model_status'],'unavailable');self.assertNotIn('Gemma',r['source']);self.assertTrue(r['drill'])
