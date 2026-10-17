import unittest,numpy as np,json
from pathlib import Path
from analyze import angles,events,resample,summarize
class ReferenceTests(unittest.TestCase):
 def test_all_input_frames_and_events(self):
  d=json.loads(Path('results/distribution.json').read_text());self.assertEqual(d['n'],219)
  for r in d['records']:
   p=np.load(Path('source/data/keypoints')/r['filename'],allow_pickle=False);a=angles(p);v,_=events(p,a)
   self.assertTrue(np.all(np.diff(v)>0));self.assertEqual(v[-1],len(p)-1)
   aligned=resample(a,v)
   for t,f in [(0,0),(40,v[1]),(80,v[3]),(100,len(p)-1)]:np.testing.assert_allclose(aligned[t],a[f],atol=1e-8)
 def test_averages_use_every_serve(self):
  d=json.loads(Path('results/distribution.json').read_text());a=np.load('results/aligned_trajectories.npz')['phase_angles']
  np.testing.assert_allclose(d['groups']['All']['phase']['mean'],a.mean(axis=0),atol=.0051)
  self.assertEqual(d['groups']['First serves']['n']+d['groups']['Second serves']['n'],219)
 def test_quantiles_and_std(self):
  x=np.arange(24).reshape(3,4,2);s=summarize(x)
  np.testing.assert_allclose(s['sd'],x.std(axis=0,ddof=1),atol=.0051)
  self.assertTrue(np.all(np.array(s['p10'])<=np.array(s['p90'])))
if __name__=='__main__':unittest.main()
