import unittest
import numpy as np
from pipeline import angle,dtw,validate_pose
class PipelineTests(unittest.TestCase):
    def test_angles(self):
        o=np.zeros(3)
        self.assertAlmostEqual(float(angle(np.array([1,0,0]),o,np.array([0,1,0]))),90)
        self.assertAlmostEqual(float(angle(np.array([1,0,0]),o,np.array([-1,0,0]))),180)
    def test_degenerate(self):
        with self.assertRaises(ValueError):angle(np.zeros(3),np.zeros(3),np.ones(3))
    def test_invalid_pose(self):
        for p in [np.zeros((3,16,3)),np.full((3,17,3),np.nan),np.zeros((1,17,3))]:
            with self.assertRaises(ValueError):validate_pose(p)
    def test_time_warp(self):
        a=np.array([[0.],[30.],[60.],[90.]])
        b=np.repeat(a,2,axis=0)
        path,error=dtw(a,b)
        np.testing.assert_allclose(error,0)
        np.testing.assert_array_equal(path[0],[0,0]);np.testing.assert_array_equal(path[-1],[3,7])
        self.assertTrue(np.all(np.diff(path,axis=0)>=0))
if __name__=='__main__':unittest.main()
