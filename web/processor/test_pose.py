import unittest
import numpy as np
from pose import crop_input,decode

class PoseTests(unittest.TestCase):
    def test_preprocessing_keeps_bgr_and_preserves_aspect(self):
        image=np.full((720,1280,3),[10,20,30],dtype=np.uint8)
        blob,matrix=crop_input(image,[.4,.2,.6,.8])
        self.assertEqual(blob.shape,(1,3,256,192))
        np.testing.assert_allclose(blob[0,:,100,100],[10,20,30])
        self.assertAlmostEqual(matrix[0,0],matrix[1,1])
        np.testing.assert_allclose(matrix@np.array([96,128,1]),[640,360])

    def test_simcc_decoding_returns_source_pixels_and_minimum_score(self):
        px=np.zeros((133,384));py=np.zeros((133,512))
        px[:,20]=.8;py[:,40]=.6
        xy,scores=decode(px,py,np.array([[.5,0,100],[0,.5,200]]))
        self.assertEqual(xy.shape,(17,2))
        np.testing.assert_allclose(xy,np.tile([105,210],(17,1)))
        np.testing.assert_allclose(scores,.6)

if __name__=='__main__':unittest.main()
