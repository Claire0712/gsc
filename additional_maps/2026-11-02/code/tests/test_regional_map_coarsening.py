import unittest
import pandas as pd,numpy as np
from scripts.check_regional_map_coarsening_20261102 import coarsen,FIELDS
class CoarseConservation(unittest.TestCase):
 def test_native_weights_and_means_conserved(self):
  f=pd.DataFrame(dict(country_id=['USA']*3,longitude=[-100,-99.75,-99],latitude=[40,40.25,40],country_population_weight=[1.,3.,2.],**{k:[0.,4.,2.] for k in FIELDS}));g=coarsen(f,.5);self.assertEqual(len(g),2);self.assertEqual(g.country_population_weight.sum(),6)
  for k in FIELDS:self.assertAlmostEqual(np.average(f[k],weights=f.country_population_weight),np.average(g[k],weights=g.country_population_weight))
 def test_countries_never_merged(self):
  f=pd.DataFrame(dict(country_id=['USA','CHN'],longitude=[1.,1.],latitude=[1.,1.],country_population_weight=[1.,2.],**{k:[1.,3.] for k in FIELDS}));self.assertEqual(len(coarsen(f,1)),2)
if __name__=='__main__':unittest.main()
