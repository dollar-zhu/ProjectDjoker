import unittest
import numpy as np
from rear_view import rear_view

class RearViewTests(unittest.TestCase):
    def pose(self):
        p=np.zeros((101,17,3))
        p[:,1]=[.3,0,0];p[:,4]=[-.3,0,0]
        p[:,8]=[0,0,1];p[:,14]=[.4,0,1];p[:,11]=[-.4,0,1]
        p[:,16]=[.6,.3,1.5]
        return p

    def test_rear_orientation_is_rotation_invariant_and_preserves_geometry(self):
        p=self.pose();a=1.9;c,s=np.cos(a),np.sin(a)
        rotated=p.copy();rotated[:,:,:2]=p[:,:,:2]@np.array([[c,-s],[s,c]])
        out,info=rear_view(rotated)
        np.testing.assert_allclose(out,p,atol=1e-8)
        self.assertEqual(info['view'],'rear')
        self.assertEqual(info['sourceView'],'unknown')
        self.assertGreater(out[90,1,0],out[90,4,0])
        np.testing.assert_allclose(np.linalg.norm(out[:,16]-out[:,11],axis=1),np.linalg.norm(rotated[:,16]-rotated[:,11],axis=1))

    def test_unstable_or_degenerate_orientation_is_excluded(self):
        p=self.pose();p[85::2,1]*=-1;p[85::2,4]*=-1
        self.assertIsNone(rear_view(p)[0])
        p=self.pose();p[:,1]=p[:,4]
        self.assertIsNone(rear_view(p)[0])
