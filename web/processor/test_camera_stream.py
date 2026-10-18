import unittest
import cv2
import numpy as np
from live_capture import JpegFrames

class CameraStreamTests(unittest.TestCase):
    def jpeg(self,bgr):
        return cv2.imencode('.jpg',np.full((32,40,3),bgr,np.uint8))[1].tobytes()

    def test_fragmented_frames_ignore_diagnostics_and_preserve_color(self):
        red,green=self.jpeg((0,0,255)),self.jpeg((0,255,0))
        wire=b'camera diagnostic\r\n'+red+b'warning\n'+green
        parser=JpegFrames();frames=[]
        for i in range(0,len(wire),113): frames.extend(parser.feed(wire[i:i+113]))
        self.assertEqual(len(frames),2)
        for raw,channel in zip(frames,[2,1]):
            image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
            self.assertEqual(image.shape,(32,40,3))
            self.assertEqual(int(image.mean((0,1)).argmax()),channel)

    def test_recovers_at_next_frame_after_truncated_jpeg(self):
        raw=self.jpeg((255,0,0));parser=JpegFrames()
        frames=parser.feed(b'\xff\xd8broken frame'+raw)
        self.assertEqual(frames,[raw])

    def test_incomplete_input_is_bounded(self):
        parser=JpegFrames();parser.feed(b'\xff\xd8'+b'x'*3_000_000)
        self.assertLess(len(parser.buffer),2_000_000)

if __name__=='__main__':unittest.main()
