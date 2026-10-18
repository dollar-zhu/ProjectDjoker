import unittest
import json
from pathlib import Path
import numpy as np
from capture import ServeCapture, pose_signal


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.detector = ServeCapture()

    def step(self, t, present=True, overhead=False, lowered=True):
        return self.detector.update(t, present, overhead, lowered)

    def start(self):
        self.assertIsNone(self.step(0))
        self.assertEqual(self.step(.5), 'start')

    def test_presence_must_be_sustained(self):
        self.step(0)
        self.step(.3, False)
        self.assertIsNone(self.step(.6))
        self.assertEqual(self.step(1.2), 'start')

    def test_standing_never_completes_a_serve(self):
        self.start()
        self.assertIsNone(self.step(3))
        self.assertEqual(self.step(18.6), 'discard')

    def test_overhead_then_followthrough_finishes_with_tail(self):
        self.start()
        self.step(1, overhead=True, lowered=False)
        self.step(1.2, overhead=True, lowered=False)
        self.step(1.4)
        self.assertIsNone(self.step(1.8))
        self.assertEqual(self.step(2.3), 'complete')
        self.assertIsNone(self.step(2.4))
        self.assertEqual(self.detector.state, 'cooldown')

    def test_fast_overhead_motion_at_camera_frame_rate(self):
        self.start()
        self.step(1, overhead=True, lowered=False)
        self.step(1 + 1/15, overhead=True, lowered=False)
        self.step(1.2)
        self.step(1.5)
        self.step(1.8)
        self.assertEqual(self.step(2.1), 'complete')

    def test_brief_occlusions_do_not_reset_observed_followthrough(self):
        self.start()
        self.step(1,overhead=True,lowered=False)
        self.step(1.1,overhead=True,lowered=False)
        events=[]
        for t in np.arange(1.3,2.21,.05):
            hidden=1.55<=t<1.7 or 1.85<=t<1.95
            event=self.step(float(t),lowered=not hidden)
            if event:events.append((t,event))
        self.assertEqual([e for _,e in events],['complete'])
        self.assertGreaterEqual(events[0][0],2.1)

    def test_occluded_finish_cannot_complete_on_elapsed_time_alone(self):
        self.start()
        self.step(1,overhead=True,lowered=False)
        self.step(1.1,overhead=True,lowered=False)
        self.step(1.3)
        for t in np.arange(1.35,3,.05):
            self.assertIsNone(self.step(float(t),lowered=False))
        self.assertIsNone(self.step(3.1))

    def test_long_observation_gap_cannot_invent_followthrough(self):
        self.start()
        self.step(1,overhead=True,lowered=False)
        self.step(1.1,overhead=True,lowered=False)
        self.step(1.3)
        self.assertNotEqual(self.step(2.5),'complete')

    def test_live_crop_follows_player_and_holds_through_brief_loss(self):
        import capture
        self.assertTrue(hasattr(capture,'PlayerCrop'), 'Live tracking must crop before inference')
        tracker=capture.PlayerCrop([0,0,1,1])
        xy=np.full((17,2),[320.,240.])
        box=tracker.update(0,xy,True,640,480)
        self.assertEqual(box,[.21875,0,.78125,1])
        self.assertEqual(tracker.update(.5,xy,False,640,480),box)
        self.assertEqual(tracker.update(1.1,xy,False,640,480),[0,0,1,1])
        explicit=capture.PlayerCrop([.1,.1,.8,.9])
        self.assertEqual(explicit.update(0,xy,True,640,480),[.1,.1,.8,.9])

    def test_recorded_rear_serve_stops_after_visible_followthrough(self):
        fixture=json.loads((Path(__file__).parent/'fixtures/rear_serve_finish.json').read_text())
        # Drop alternate observations, retaining the real final observation.
        for stride in [1,2]:
            with self.subTest(stride=stride):
                detector=ServeCapture();events=[]
                frames=fixture['frames'][::stride]
                if frames[-1]!=fixture['frames'][-1]:frames=frames+[fixture['frames'][-1]]
                for t,present,overhead,lowered in frames:
                    event=detector.update(t,present,overhead,lowered)
                    if event:events.append((t,event))
                self.assertEqual([e for _,e in events],['start','complete'])
                self.assertGreaterEqual(events[-1][0],fixture['expected_stop'][0])
                self.assertLessEqual(events[-1][0],fixture['expected_stop'][1])

    def test_single_overhead_spike_does_not_finish(self):
        self.start()
        self.step(1, overhead=True, lowered=False)
        self.step(1.1)
        self.assertIsNone(self.step(3))

    def test_tracking_loss_cannot_count_as_followthrough(self):
        self.start()
        self.step(1, overhead=True, lowered=False)
        self.step(1.2, overhead=True, lowered=False)
        self.step(1.4, False)
        self.assertEqual(self.step(2.6, False), 'discard')

    def test_return_to_overhead_resets_finish_timer(self):
        self.start()
        self.step(1, overhead=True, lowered=False)
        self.step(1.2, overhead=True, lowered=False)
        self.step(1.4)
        self.step(1.8, overhead=True, lowered=False)
        self.step(2)
        self.assertIsNone(self.step(2.4))
        self.assertEqual(self.step(2.9), 'complete')

    def test_cooldown_rearms_without_leaving_frame(self):
        self.test_overhead_then_followthrough_finishes_with_tail()
        self.step(4.4)
        self.assertEqual(self.step(5), 'start')

    def test_pose_requires_visible_body_and_hitting_arm(self):
        xy=np.array([[320,100]]*17,dtype=float)
        xy[5:7]=[[280,180],[360,180]]
        xy[7:11]=[[270,230],[370,230],[270,300],[370,300]]
        xy[11:17]=[[290,270],[350,270],[290,350],[350,350],[290,430],[350,430]]
        scores=np.ones(17)
        self.assertEqual(pose_signal(xy,scores,640,480,'right'), (True,False,True))
        xy[10]=[370,50]
        self.assertEqual(pose_signal(xy,scores,640,480,'right'), (True,True,False))
        scores[10]=.1
        self.assertEqual(pose_signal(xy,scores,640,480,'right'), (True,False,False))
        scores[10]=1;scores[8]=.1
        self.assertEqual(pose_signal(xy,scores,640,480,'right'), (True,True,False))
        scores[8]=1
        scores[16]=.1
        self.assertFalse(pose_signal(xy,scores,640,480,'right')[0])
        scores[16]=1;xy[16]=[350,490]
        self.assertFalse(pose_signal(xy,scores,640,480,'right')[0])

if __name__=='__main__': unittest.main()

class ManualCaptureTests(unittest.TestCase):
    def test_manual_recording_ignores_tracking_until_user_finishes(self):
        from capture import ManualCapture
        gate=ManualCapture()
        self.assertIsNone(gate.update(0))
        self.assertEqual(gate.update(1,'record'),'start')
        self.assertIsNone(gate.update(5))
        self.assertEqual(gate.state,'recording')
        self.assertEqual(gate.update(6,'finish'),'complete')
        self.assertEqual(gate.state,'ready')
        self.assertIsNone(gate.update(7))
        self.assertEqual(gate.completion,'manual_stop')

    def test_manual_limit_saves_instead_of_discarding(self):
        from capture import ManualCapture
        gate=ManualCapture();gate.update(1,'record')
        self.assertEqual(gate.update(20),'complete')
        self.assertEqual(gate.completion,'manual_duration_limit')

    def test_early_finish_preserves_minimum_decodable_clip(self):
        from capture import ManualCapture
        gate=ManualCapture();gate.update(1,'record')
        self.assertIsNone(gate.update(1.1,'finish'))
        self.assertEqual(gate.update(1.6),'complete')
