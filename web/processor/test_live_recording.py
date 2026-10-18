import json
import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
from live_capture import TimedRecording, save_review

class RecordingTests(unittest.TestCase):
    def test_live_review_uses_recorded_player_extent_for_crop(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path=root/'capture.avi'
            recorder=TimedRecording(path,(64,48),15)
            for n in range(20): recorder.add(n/15,np.full((48,64,3),100,np.uint8))
            recorder.close()
            xy=[[20+i,20] for i in range(17)]
            trace=[{'time':n/15,'present':True,'xy':xy,'scores':[.9]*17} for n in range(20)]
            # A partial-body walk-in must not expand the player area to the room.
            trace.insert(0,{'time':0,'present':False,'xy':[[0,0]]*17,'scores':[.9]*17})
            options={'crop':[0,0,1,1],'view':'rear','handedness':'right'}
            job=save_review(root,path,options,'manual_stop',trace)
            data=json.loads((root/job/'job.json').read_text())
            self.assertGreater(data['options']['crop'][0],0)
            self.assertLess(data['options']['crop'][2],.8)
            self.assertEqual(data['options']['crop'][1::2],[0,1], 'Keep room for raised hands and feet')
            self.assertEqual(options['crop'],[0,0,1,1], 'Do not change live camera options')

    def test_recording_preserves_elapsed_time_when_frames_drop(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'capture.avi'
            recorder=TimedRecording(path, (64,48), 15)
            for t in [10,10.1,10.3,10.6,11.0]:
                recorder.add(t,np.full((48,64,3),100,np.uint8))
            recorder.close()
            cap=cv2.VideoCapture(str(path))
            self.assertTrue(cap.isOpened())
            self.assertAlmostEqual(cap.get(cv2.CAP_PROP_FRAME_COUNT)/cap.get(cv2.CAP_PROP_FPS),16/15)
            cap.release()

    def test_completed_capture_becomes_existing_review_job(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path=root/'capture.avi'
            recorder=TimedRecording(path, (64,48), 15)
            for n in range(20): recorder.add(n/15,np.full((48,64,3),100,np.uint8))
            recorder.close()
            options={'crop':[0,0,1,1],'view':'side','handedness':'right'}
            job=save_review(root,path,options,'manual_stop',[{'time':0,'present':False}])
            self.assertTrue((root/job/'job.json').exists(), 'Capture must create a review job')
            data=json.loads((root/job/'job.json').read_text())
            self.assertEqual(data['status'],'ready')
            self.assertEqual(data['options'],options)
            self.assertEqual(data['capture']['completion'],'manual_stop')
            self.assertEqual(data['capture']['tracking_options'], options)
            self.assertEqual(data['capture']['tracking_image_size'], [64,48])
            self.assertEqual(json.loads((root/job/'tracking.json').read_text()),[{'time':0,'present':False}])
            self.assertTrue((root/job/'video.mp4').exists())
            self.assertFalse(path.exists())

if __name__=='__main__': unittest.main()
