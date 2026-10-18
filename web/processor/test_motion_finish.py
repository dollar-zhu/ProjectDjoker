import json
from pathlib import Path
import unittest
import inspect
import numpy as np
import capture
from stages import movement_stages
from test_ready_capture import standing_pose


def recordings():
    data=json.loads((Path(__file__).parent/'fixtures/occluded_followthrough.json').read_text())
    for item in data['recordings']:
        pose=np.asarray(item['pose'],float);scores=np.asarray(item['scores'],float)
        pose[scores<.5]=np.nan
        yield item,np.asarray(item['times']),pose


class MotionFinishTests(unittest.TestCase):
    def detector(self):
        self.assertTrue(hasattr(capture,'MotionFinish'), 'Need temporal multi-joint recovery evidence')
        return capture.MotionFinish()

    def test_saved_serve_finishes_despite_occluded_wrist(self):
        for item,t,p in recordings():
            with self.subTest(recording=item['id']):
                gate=self.detector();events=[]
                for stamp,pose in zip(t,p):
                    event=gate.update(stamp,pose)
                    if event:events.append((stamp,event))
                self.assertEqual([event for _,event in events],['descent','complete'])
                self.assertLessEqual(events[-1][0],t[-1])
                self.assertTrue(gate.evidence)

    def test_reach_held_missing_body_and_walking_do_not_finish(self):
        for variant in ['held','body_missing','walking','single_spike']:
            with self.subTest(variant=variant):
                gate=self.detector();events=[]
                for i in range(45):
                    pose,_=standing_pose()
                    if variant!='walking' and (i<9 if variant!='single_spike' else i==0):
                        pose[10,1]=50;pose[8,1]=135
                    if variant=='held':pose[10,1]=50;pose[8,1]=135
                    if variant=='body_missing' and i>=9:pose[:]=np.nan
                    event=gate.update(i/30,pose)
                    if event:events.append(event)
                self.assertNotIn('complete',events)

    def test_hidden_wrist_does_not_allow_static_elbow_to_invent_descent(self):
        gate=self.detector()
        for i in range(60):
            pose,_=standing_pose();pose[8,1]=135
            pose[10,1]=50 if i<10 else np.nan
            self.assertIsNone(gate.update(i/30,pose))

    def test_missing_knees_and_feet_do_not_erase_visible_arm_recovery(self):
        for item,t,p in recordings():
            with self.subTest(recording=item['id']):
                gate=self.detector();p[:,13:17]=np.nan;events=[]
                for stamp,pose in zip(t,p):
                    event=gate.update(stamp,pose)
                    if event:events.append(event)
                self.assertIn('complete',events)

    def test_offline_stages_use_observed_elbow_recovery_across_wrist_gap(self):
        for item,t,p in recordings():
            with self.subTest(recording=item['id']):
                reach=int(np.argmin(abs(t-item['reach_time'])))
                by={s['id']:s for s in movement_stages(t,p,0,reach)}
                self.assertEqual(by['follow_through']['status'],'estimated')
                self.assertEqual(by['finish']['status'],'estimated')
                self.assertTrue(by['follow_through']['evidence'])

    def test_live_gate_completes_with_missing_feet_and_occluded_wrist(self):
        self.assertIn('pose',inspect.signature(capture.ReadyServeCapture.update).parameters)
        for item,t,p in recordings():
            gate=capture.ReadyServeCapture()
            # Exercise the public ready/countdown lifecycle before replaying motion.
            for stamp in np.arange(t[0]-4,t[0]-.1,.1):
                gate.update(float(stamp),True,False,True,stamp<t[0]-3.1)
            self.assertEqual(gate.state,'recording')
            p[:,13:17]=np.nan
            events=[]
            for stamp,pose in zip(t,p):
                event=gate.update(float(stamp),False,False,False,False,pose=pose)
                if event:events.append(event)
            self.assertEqual(events,['complete'],item['id'])

    def test_saved_f90_score_and_stage_boundary_are_identical(self):
        path=Path(__file__).parents[1]/'src/lib/fixtures/serve-similarity-f90.json'
        data=json.loads(path.read_text())
        t=np.asarray([f['time'] for f in data['frames']])
        p=np.asarray([f['xy'] for f in data['frames']],float)
        scores=np.asarray([f['scores'] for f in data['frames']])
        p[scores<.5]=np.nan
        events={e['id']:e['time'] for e in data['events']}
        load=int(np.argmin(abs(t-events['loading'])));reach=int(np.argmin(abs(t-events['reach'])))
        result=movement_stages(t,p,load,reach)
        self.assertEqual(result[-1]['end'],4.25)
        self.assertIn('elbow_descent_torso_lengths',result[-1]['evidence'][0]['measurements'])

    def test_blind_frames_after_descent_cannot_finish(self):
        gate=self.detector();events=[]
        for i in range(60):
            pose,_=standing_pose()
            if i<8:pose[10,1]=50;pose[8,1]=135
            elif i>=13:pose[:]=np.nan
            event=gate.update(i/30,pose)
            if event:events.append(event)
        self.assertNotIn('complete',events)

    def test_two_frame_reach_at_twenty_fps_is_not_mistaken_for_single_spike(self):
        gate=self.detector();events=[]
        for i in range(15):
            pose,_=standing_pose()
            if i<2:pose[10,1]=50;pose[8,1]=135
            event=gate.update(i/20,pose)
            if event:events.append(event)
        self.assertEqual(events,['descent','complete'])


if __name__=='__main__':unittest.main()
