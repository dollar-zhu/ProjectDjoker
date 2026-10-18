import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from review import review
from test_review import sequence


def full_sequence():
    t,p,c=sequence()
    p[:,9,1]=150-110*np.clip((t-.35)/.5,0,1)
    return t,p,c


class StageTests(unittest.TestCase):
    def test_hidden_toss_wrist_does_not_turn_loading_pause_into_setup(self):
        data=json.loads((Path(__file__).parent/'fixtures/serve-setup-2b7.json').read_text())
        t=np.asarray([f['time'] for f in data['frames']])
        p=np.asarray([f['xy'] for f in data['frames']])
        c=np.asarray([f['scores'] for f in data['frames']])
        with tempfile.TemporaryDirectory() as d:
            result=review(Path(d),t,p,c,'rear','right',[640,480])
        stages={s['id']:s for s in result['stages']}
        self.assertEqual(stages['setup']['status'],'estimated')
        self.assertLess(stages['setup']['time'],1.85,'Setup must precede the visible arm raise, not mark the loading pause')
        self.assertEqual(stages['setup']['time'],1.8083,'Keep browser comparison fixture in sync')
        self.assertEqual(stages['toss']['status'],'unavailable','Do not fabricate an occluded wrist trajectory')
        self.assertEqual(stages['finish']['status'],'estimated')

    def test_raised_tossing_arm_cannot_be_labelled_as_setup(self):
        t,p,c=full_sequence();p[:,9,1]=30;p[:,7,1]=60
        result=self.analyse(t,p,c)
        self.assertEqual(result['stages'][0]['status'],'unavailable')

    def analyse(self,t,p,c):
        with tempfile.TemporaryDirectory() as d:
            return review(Path(d),t,p,c,'rear','right',[240,300])

    def test_complete_movement_has_six_evidence_linked_stages(self):
        r=self.analyse(*full_sequence())
        self.assertIn('stages',r)
        stages=r['stages']
        self.assertEqual([s['id'] for s in stages],['setup','toss','loading','acceleration','follow_through','finish'])
        self.assertTrue(all(s['status']=='estimated' for s in stages),stages)
        self.assertEqual(sorted(s['time'] for s in stages),[s['time'] for s in stages])
        for s in stages:
            self.assertLessEqual(s['start'],s['time']);self.assertLessEqual(s['time'],s['end'])
            self.assertTrue(s['evidence']);self.assertEqual(s['frame'],round(s['time']*30))
        self.assertEqual([e['id'] for e in r['events']],['loading','reach'])
        json.dumps(r,allow_nan=False)

    def test_invisible_toss_does_not_invent_release_or_lose_loading(self):
        t,p,c=full_sequence();c[:,9]=.1
        r=self.analyse(t,p,c)
        self.assertIn('stages',r)
        by={s['id']:s for s in r['stages']}
        self.assertEqual(by['toss']['status'],'unavailable');self.assertIsNone(by['toss']['time'])
        self.assertEqual(by['loading']['status'],'estimated')
        self.assertEqual(by['toss']['evidence'],[])

    def test_hidden_followthrough_does_not_become_a_finish(self):
        t,p,c=full_sequence();c[t>2.1,10]=.1
        r=self.analyse(t,p,c)
        self.assertIn('stages',r)
        for s in r['stages'][-2:]:
            self.assertEqual(s['status'],'unavailable');self.assertIsNone(s['frame'])

    def test_times_and_frame_indices_survive_walk_in_trim(self):
        t,p,c=full_sequence();prefix=np.repeat(p[:1],60,axis=0);prefix[:,:,1]=-50
        p=np.concatenate([prefix,p]);c=np.full((len(p),17),.9)
        r=self.analyse(np.arange(len(p))/30,p,c)
        self.assertIn('stages',r)
        for s in r['stages']:
            if s['time'] is not None:
                self.assertGreaterEqual(s['time'],2);self.assertEqual(s['frame'],round(s['time']*30))

    def test_clipped_finish_stays_unavailable(self):
        t,p,c=full_sequence();keep=t<=2.35
        r=self.analyse(t[keep],p[keep],c[keep])
        self.assertIn('stages',r)
        self.assertEqual(r['stages'][-1]['status'],'unavailable')

    def test_toss_can_be_identified_after_an_earlier_occlusion(self):
        t,p,c=full_sequence();c[(t>.2)&(t<.45),9]=.1
        r=self.analyse(t,p,c)
        self.assertEqual(r['stages'][1]['status'],'estimated')

    def test_short_wrist_gap_preserves_leg_evidence_without_claiming_complete_arm_path(self):
        t,p,c=full_sequence();c[(t>1.6)&(t<1.7),10]=.1
        r=self.analyse(t,p,c)
        self.assertEqual(r['stages'][3]['status'],'estimated')
        self.assertIn('incomplete',r['stages'][3]['detail'])
