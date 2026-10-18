"""Exercise the live loop with a deterministic camera; no USB device needed."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
import live_capture
from test_ready_capture import standing_pose


class LiveReadyCaptureTests(unittest.TestCase):
    def test_countdown_status_precedes_recording_without_preroll(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);statuses=[];recorded=[];saved_trace=[]
            model_path=root/'model.onnx';model_path.touch()
            class Camera:
                proc=SimpleNamespace(poll=lambda:None)
                n=-1
                def __init__(self,log):pass
                def read(self):
                    status=root/'live/status.json'
                    if status.exists():statuses.append(json.loads(status.read_text()))
                    self.n+=1
                    if self.n>55:
                        (root/'live/stop').touch()
                        return None
                    return 100+self.n/10,np.zeros((480,640,3),np.uint8)
                def close(self):pass
            camera=Camera(None)
            class Model:
                def get_inputs(self):return [SimpleNamespace(shape=[1,3,256,192],name='input')]
                def run(self,*args):return None,None
            class Recorder:
                start=None
                def __init__(self,*args):pass
                def add(self,t,image):
                    if self.start is None:self.start=t
                    recorded.append(t)
                def close(self):pass
            def decode(*args):
                xy,scores=standing_pose()
                if camera.n<=8:xy[10,1]=180
                if 42<=camera.n<=43:xy[10,1]=50
                return xy,scores
            def save_review(root,path,options,completion,tracking):
                saved_trace.extend(tracking)
                return 'test-review'
            with (patch.object(live_capture,'BoardCamera',return_value=camera),
                  patch.object(live_capture,'ONNX',model_path),
                  patch.object(live_capture,'TimedRecording',Recorder),
                  patch.object(live_capture,'decode',side_effect=decode),
                  patch.object(live_capture,'save_review',side_effect=save_review),
                  patch.object(live_capture,'process'),
                  patch('onnxruntime.InferenceSession',return_value=Model()),
                  patch.object(live_capture.time,'monotonic',side_effect=lambda:100+camera.n/10)):
                live_capture.run(root,{'mode':'auto','view':'side','handedness':'right','crop':[0,0,1,1]})
            countdowns=[s['countdown'] for s in statuses if s['state']=='countdown']
            self.assertEqual(set(countdowns),{3,2,1})
            self.assertAlmostEqual(recorded[0],103.8)
            self.assertTrue(any(s['state']=='recording' for s in statuses))
            self.assertTrue(any(s['state']=='cooldown' for s in statuses))
            self.assertEqual(saved_trace[0]['time'],0)
            self.assertEqual(saved_trace[0]['auto_event'],'start')
            self.assertFalse(any(frame['ready'] for frame in saved_trace))
            self.assertEqual(saved_trace[-1]['auto_event'],'complete')
            self.assertEqual(json.loads((root/'live/status.json').read_text())['state'],'stopped')


if __name__=='__main__':unittest.main()
