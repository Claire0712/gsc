import unittest
import importlib.util
import numpy as np

class HourSufficientTests(unittest.TestCase):
 def module(self):
  self.assertIsNotNone(importlib.util.find_spec('scripts.hour_sufficient'),'hourly sufficient-statistic implementation absent')
  from scripts import hour_sufficient
  return hour_sufficient
 def test_slot_transform_not_threshold_of_mean(self):
  m=self.module();r=np.tile([0.,.94,.95,1.,1.1,2.],24)
  out=m.summarize(np.arange(144)*600,r,np.ones(144),np.ones(144,dtype=bool),0)
  self.assertEqual(len(out['hour']),24)
  np.testing.assert_allclose(out['below95'],1/3)
  np.testing.assert_allclose(out['deficit'],1.11/6)
  np.testing.assert_array_equal(out['count'],6)
 def test_reject_missing_or_unavailable_slot(self):
  m=self.module();t=np.arange(144)*600;v=np.ones(144);a=np.ones(144,dtype=bool)
  with self.assertRaises(ValueError):m.summarize(t[:-1],v[:-1],v[:-1],a[:-1],0)
  a[7]=False
  with self.assertRaises(ValueError):m.summarize(t,v,v,a,0)
 def test_compressed_equals_expanded_weighted_fit_and_rss(self):
  m=self.module();rng=np.random.default_rng(731);r=rng.uniform(.5,1.5,144)
  out=m.summarize(np.arange(144)*600,r,np.ones(144),np.ones(144,dtype=bool),0)
  x=np.c_[np.ones(24),rng.normal(size=24)];w=rng.uniform(.2,1,24)
  for name,y in [('signed',r-1),('deficit',np.maximum(0,1-r)),('below95',(r<.95).astype(float))]:
   xx=np.repeat(x,6,axis=0);ww=np.repeat(w,6);b=np.linalg.lstsq(xx*np.sqrt(ww)[:,None],y*np.sqrt(ww),rcond=None)[0]
   c=np.linalg.lstsq(x*np.sqrt(w*6)[:,None],out[name]*np.sqrt(w*6),rcond=None)[0]
   np.testing.assert_allclose(b,c,atol=1e-12)
   np.testing.assert_allclose(np.sum(ww*(y-xx@b)**2),np.sum(w*6*(out[name]-x@c)**2)+np.sum(w*out[name+'_within_ss']),atol=1e-12)
