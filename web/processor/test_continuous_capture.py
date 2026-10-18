"""Continuous capture: repeated serves without a ready gesture."""
import json
from pathlib import Path
import unittest
import numpy as np
import capture
from test_ready_capture import standing_pose


def pose(wrist_y=300):
    xy,_=standing_pose();xy[10,1]=wrist_y
    return xy


class ContinuousCaptureTests(unittest.TestCase):
    def setUp(self):
        self.gate=capture.ContinuousServeCapture()
        self.events=[]

    def run_frames(self,start,stop,wrist_y=300,present=True,body=True):
        for t in np.arange(start,stop-1e-9,.1):
            p=pose(wrist_y) if body else np.full((17,2),np.nan)
            event=self.gate.update(round(float(t),3),present,wrist_y<180,p)
            if event:self.events.append((event,round(float(t),3)))

    def serve(self,start):
        """Settled stance, a brief reach, then an observed descent and recovery."""
        self.run_frames(start,start+1.5)
        self.run_frames(start+1.5,start+1.7,wrist_y=50)
        self.run_frames(start+1.7,start+2.5)

    def test_settled_stance_then_serve_is_captured_with_reach_onset(self):
        self.serve(0)
        self.assertEqual([e for e,_ in self.events],['start','complete'])
        self.assertAlmostEqual(self.gate.onset,1.5)
        self.assertAlmostEqual(self.gate.clip_start,0,msg='Pre-roll is bounded by the settled stance')
        self.assertEqual(self.gate.captured,1)
        self.assertEqual(self.gate.state,'cooldown')

    def test_repeated_serves_need_no_gesture(self):
        for start in [0,4,8]:
            self.serve(start)
            self.assertGreaterEqual(self.gate.clip_start,start,'No clip reaches into the previous serve')
        self.assertEqual([e for e,_ in self.events],['start','complete']*3)
        self.assertEqual(self.gate.captured,3)

    def test_walk_in_with_raised_arm_cannot_start(self):
        self.run_frames(0,.5,wrist_y=50)
        self.run_frames(.5,1.2)
        self.assertEqual(self.gate.state,'waiting')
        self.run_frames(1.2,1.4,wrist_y=50)
        self.run_frames(1.4,2.2)
        self.assertEqual(self.events,[])

    def test_flickering_visibility_still_settles(self):
        for t in np.arange(0,1.5,.1):
            t=round(float(t),3)
            self.gate.update(t,round(t*10)%3!=2,False,pose())
        self.assertEqual(self.gate.state,'watching')
        self.run_frames(1.5,1.7,wrist_y=50)
        self.assertEqual([e for e,_ in self.events],['start'])

    def test_sustained_loss_restarts_settling(self):
        self.run_frames(0,.8)
        self.run_frames(.8,1.2,present=False)
        self.run_frames(1.2,2)
        self.assertEqual(self.gate.state,'waiting')

    def test_held_overhead_arm_is_discarded_and_must_settle_again(self):
        self.run_frames(0,1.2)
        self.run_frames(1.2,4,wrist_y=50)
        self.assertEqual([e for e,_ in self.events],['start','discard'])
        self.run_frames(4,6,wrist_y=50)
        self.assertEqual(self.gate.state,'waiting')
        self.assertEqual(len(self.events),2,'A still-raised arm cannot rearm')

    def test_transport_gap_discards_recording(self):
        self.run_frames(0,1.2)
        self.run_frames(1.2,1.4,wrist_y=50)
        self.assertEqual(self.gate.update(2.5,True,False,pose()),'discard')
        self.assertEqual(self.gate.state,'waiting')

    def test_sustained_absence_disarms_but_brief_loss_does_not(self):
        self.run_frames(0,1.2)
        self.assertEqual(self.gate.state,'watching')
        self.run_frames(1.2,1.6,present=False)
        self.assertEqual(self.gate.state,'watching')
        self.run_frames(1.6,2.8,present=False,body=False)
        self.assertEqual(self.gate.state,'waiting')

    def test_body_loss_during_recording_discards(self):
        self.run_frames(0,1.2)
        self.run_frames(1.2,1.4,wrist_y=50)
        self.run_frames(1.4,2.6,present=False,body=False)
        self.assertEqual([e for e,_ in self.events],['start','discard'])

    def test_saved_live_serve_is_captured_with_its_setup(self):
        """Pose replay of a real live recording; the pre-roll keeps setup through finish."""
        data=json.loads((Path(__file__).parent/'fixtures/live-serve-168.json').read_text())
        setup=0.83
        events=[]
        for f in data['frames']:
            xy,scores=np.asarray(f['xy'],float),np.asarray(f['scores'],float)
            present,overhead,_=capture.pose_signal(xy,scores,640,480,'right')
            observed=xy.copy();observed[scores<.5]=np.nan
            event=self.gate.update(f['time'],present,overhead,observed)
            if event:events.append((event,f['time']))
        self.assertEqual([e for e,_ in events],['start','complete'])
        self.assertLessEqual(self.gate.onset-self.gate.PRE,setup)


    def test_clipped_reach_warns_about_framing(self):
        import live_capture
        xy,_=standing_pose()
        row=lambda y,state:{'xy':[[0,0]]*10+[[300,y]]+[[0,0]]*6,'auto_state':state}
        self.assertIsNone(live_capture.framing_warning([row(0,'watching'),row(40,'recording')]))
        self.assertIn('top of the frame',live_capture.framing_warning([row(0,'recording')]))


if __name__=='__main__':unittest.main()
