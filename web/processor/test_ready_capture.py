"""Deliberate ready cues and evidence-gated automatic capture."""
import unittest
import json
from pathlib import Path
import numpy as np
import capture


def standing_pose():
    xy=np.array([[320,100]]*17,dtype=float)
    xy[5:7]=[[280,180],[360,180]]
    xy[7:11]=[[270,230],[370,230],[270,300],[370,300]]
    xy[11:17]=[[290,270],[350,270],[290,350],[350,350],[290,430],[350,430]]
    return xy,np.ones(17)


class ReadyPoseTests(unittest.TestCase):
    def signal(self,xy,scores):
        self.assertTrue(hasattr(capture,'ready_pose'), 'Need deliberate ready cue separate from serve signal')
        return capture.ready_pose(xy,scores,640,480)

    def test_either_hand_at_shoulder_is_ready(self):
        for wrist in [9,10]:
            xy,scores=standing_pose();xy[wrist,1]=180
            self.assertTrue(self.signal(xy,scores))

    def test_walking_and_overhead_serve_are_not_ready(self):
        xy,scores=standing_pose()
        self.assertFalse(self.signal(xy,scores))
        xy[10,1]=50
        self.assertFalse(self.signal(xy,scores))

    def test_hidden_hand_or_partial_body_cannot_trigger(self):
        xy,scores=standing_pose();xy[10,1]=180
        scores[10]=.2
        self.assertFalse(self.signal(xy,scores))
        scores[10]=1;scores[16]=.2
        self.assertFalse(self.signal(xy,scores))
        scores[16]=1;xy[16,1]=490
        self.assertFalse(self.signal(xy,scores))


class ReadyCaptureTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(capture,'ReadyServeCapture'), 'Automatic capture needs a ready/countdown gate')
        self.gate=capture.ReadyServeCapture()

    def step(self,t,present=True,ready=False,overhead=False,lowered=True):
        return self.gate.update(t,present,overhead,lowered,ready)

    def countdown(self):
        for t in np.arange(0,.81,.1):
            self.assertIsNone(self.step(float(t),ready=True))
        self.assertEqual(self.gate.state,'countdown')
        self.assertEqual(self.gate.countdown,3)

    def start(self):
        self.countdown()
        events=[]
        for t in np.arange(.9,3.91,.1):
            event=self.step(float(t))
            if event:events.append(event)
        self.assertEqual(events,['start'])
        self.assertEqual(self.gate.state,'recording')
        self.assertIsNone(self.gate.countdown)
        self.assertEqual(self.gate.ready_progress,0)

    def test_presence_and_transient_gesture_do_not_record(self):
        for t in np.arange(0,3,.1):self.assertIsNone(self.step(float(t)))
        for t in np.arange(3,3.51,.1):self.assertIsNone(self.step(float(t),ready=True))
        self.step(3.6)
        self.assertEqual(self.gate.state,'waiting')
        self.assertEqual(self.gate.ready_progress,0)

    def test_existing_serve_recordings_do_not_mistake_motion_for_ready_hold(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/ready_capture_replays.json').read_text())
        for recording in fixture['recordings']:
            for stride in [1,2]:
                with self.subTest(job=recording['job'],stride=stride):
                    gate=capture.ReadyServeCapture()
                    for frame in recording['frames'][::stride]:
                        self.assertIsNone(gate.update(*frame))
                        self.assertEqual(gate.state,'waiting')

    def test_observed_hold_then_three_second_countdown(self):
        self.start()
        self.assertAlmostEqual(self.gate.started,3.8)

    def test_hand_can_remain_at_shoulder_when_countdown_ends(self):
        self.countdown()
        events=[]
        for t in np.arange(.9,4.11,.1):
            event=self.step(float(t),ready=True,lowered=False)
            if event:events.append(event)
        self.assertEqual(events,['start'])
        self.assertFalse(self.gate.saw_overhead)

    def test_observation_gap_does_not_count_toward_ready_hold(self):
        self.step(0,ready=True)
        self.step(1,ready=True)
        self.assertEqual(self.gate.state,'waiting')
        self.assertEqual(self.gate.ready_progress,0)

    def test_countdown_cancels_on_sustained_loss_and_requires_release(self):
        self.countdown()
        for t in np.arange(.9,1.51,.1):self.step(float(t),present=False)
        self.assertEqual(self.gate.state,'waiting')
        for t in np.arange(1.6,3.1,.1):self.step(float(t),ready=True)
        self.assertEqual(self.gate.state,'waiting', 'Holding the old cue must not rearm')
        for t in np.arange(3.1,3.6,.1):self.step(float(t))
        for t in np.arange(3.6,4.5,.1):self.step(float(t),ready=True)
        self.assertEqual(self.gate.state,'countdown')

    def test_countdown_survives_brief_loss_but_cannot_start_while_blind(self):
        self.countdown()
        for t in np.arange(.9,3.61,.1):self.step(float(t))
        self.assertIsNone(self.step(3.7,present=False))
        self.assertIsNone(self.step(3.8,present=False))
        self.assertEqual(self.step(3.9),'start')

    def test_camera_pause_cancels_countdown_even_if_pose_returns(self):
        self.countdown()
        self.step(3.9)
        self.assertEqual(self.gate.state,'waiting')

    def test_ready_arm_cannot_supply_overhead_evidence(self):
        self.start()
        for t in np.arange(4,6,.1):self.assertIsNone(self.step(float(t)))
        self.assertFalse(self.gate.saw_overhead)
        self.step(6,overhead=True,lowered=False)
        self.step(6.1,overhead=True,lowered=False)
        events=[]
        for t in np.arange(6.2,7.21,.1):
            event=self.step(float(t))
            if event:events.append(event)
        self.assertEqual(events,['complete'])
        self.assertEqual(self.gate.state,'cooldown')
        for t in np.arange(7.3,11,.1):self.step(float(t),ready=True)
        self.assertEqual(self.gate.state,'waiting')
        for t in np.arange(11,11.5,.1):self.step(float(t))
        for t in np.arange(11.5,12.4,.1):self.step(float(t),ready=True)
        self.assertEqual(self.gate.state,'countdown')


if __name__=='__main__':unittest.main()
