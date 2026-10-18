import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review import review


def sequence():
    times = np.arange(91) / 30
    pose = np.zeros((91,17,2))
    for i,t in enumerate(times):
        for hip,knee,ankle,x in [(11,13,15,60),(12,14,16,90)]:
            pose[i,hip] = [x,100]
            pose[i,knee] = [x+35*np.exp(-((t-1.1)/.3)**2),150]
            pose[i,ankle] = [x,200]
        pose[i,5]=[60,50];pose[i,6]=[90,50]
        pose[i,7]=[45,75];pose[i,8]=[95,55]
        pose[i,9]=[40,60]
        pose[i,10]=[100,100-130*np.exp(-((t-2)/.3)**2)]
    # Keep all points inside the image, including the overhead wrist.
    pose[:,:,1] += 50
    return times,pose,np.full((91,17),.9)


class ReviewTests(unittest.TestCase):
    def call(self, **changes):
        t,p,c=sequence()
        with tempfile.TemporaryDirectory() as d:
            return review(Path(d),changes.get('times',t),p,changes.get('scores',c),
                          changes.get('view','rear'),changes.get('handedness','right'),[240,300])

    def test_events_link_to_playback_and_strict_engine_withholds_score(self):
        result=self.call()
        self.assertEqual([x['id'] for x in result['events']],['loading','reach'])
        self.assertAlmostEqual(result['events'][0]['time'],1.1,delta=.1)
        self.assertAlmostEqual(result['events'][1]['time'],2,delta=.1)
        self.assertEqual(result['feedback']['mode'],'observation')
        self.assertIsNone(result['feedback']['rating']['score'])
        self.assertIn('reference_unvalidated',result['feedback']['reference_blocked_reasons'])
        self.assertNotIn('contact',[e['id'] for e in result['events']])
        json.dumps(result,allow_nan=False)

    def test_low_scores_abstain_instead_of_emitting_events(self):
        r=self.call(scores=np.full((91,17),.1))
        self.assertEqual(r['events'],[])
        self.assertEqual(r['feedback']['mode'],'retry')

    def test_walk_in_and_out_do_not_reject_the_visible_serve(self):
        t,p,c=sequence()
        # Recording starts/stops close to the camera, outside the full-body view.
        prefix=np.repeat(p[:1],60,axis=0);prefix[:,:,1]=-50
        pose=np.concatenate([prefix,p,prefix])
        scores=np.full((len(pose),17),.9)
        with tempfile.TemporaryDirectory() as d:
            r=review(Path(d),np.arange(len(pose))/30,pose,scores,'rear','right',[240,300])
        self.assertEqual(r['feedback']['mode'],'observation')
        self.assertAlmostEqual(r['events'][0]['time'],3.1,delta=.1)
        self.assertAlmostEqual(r['events'][1]['time'],4,delta=.1)
        self.assertEqual(r['events'][0]['frame'],round(r['events'][0]['time']*30))

    def test_missing_joints_inside_serve_still_fail_quality_gate(self):
        scores=np.full((91,17),.9);scores[20:60,15]=.1
        self.assertEqual(self.call(scores=scores)['feedback']['mode'],'retry')

    def test_occluded_wrist_before_loading_does_not_discard_visible_leg_evidence(self):
        scores=np.full((91,17),.9);scores[:50,10]=.1
        r=self.call(scores=scores)
        self.assertEqual(r['feedback']['mode'],'observation')
        self.assertEqual([e['id'] for e in r['events']],['loading','reach'])

    def test_front_view_and_unknown_handedness_do_not_get_right_handed_rules(self):
        for opts in [{'view':'front'},{'handedness':'unknown'},{'handedness':'left'}]:
            r=self.call(**opts)
            self.assertEqual(r['events'],[])
            self.assertEqual(r['feedback']['mode'],'retry')

    def test_invalid_timestamps_fail_explicitly(self):
        with self.assertRaises(ValueError): self.call(times=np.zeros(91))

    def test_retry_after_transfer_failure_reaches_transfer_again(self):
        import worker
        import uuid
        with tempfile.TemporaryDirectory() as base:
            d=Path(base)/str(uuid.uuid4());d.mkdir()
            worker.command(['ffmpeg','-v','error','-f','lavfi','-i','color=c=green:s=320x240:d=1','-c:v','libx264',str(d/'video.mp4')])
            (d/'job.json').write_text(json.dumps({'id':d.name,'options':{'crop':[0,0,1,1]},'meta':{'width':320,'height':240}}))
            real=worker.command
            def fail_transfer(args,timeout=120):
                if args[0]=='adb':
                    if 'push' in args: raise RuntimeError('simulated transfer failure')
                    return 'device'
                return real(args,timeout)
            with patch.object(worker,'command',side_effect=fail_transfer):
                for _ in range(2):
                    with self.assertRaisesRegex(RuntimeError,'simulated transfer failure'):
                        worker.process(d)

if __name__=='__main__': unittest.main()
