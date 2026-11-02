import unittest

class RegionTest(unittest.TestCase):
    def test_exact_metadata_groups_and_rejects_uncertainty(self):
        from scripts.region_samples import region_samples
        rows=[{'country_id':'AAA'},{'country_id':'BBB'},{'country_id':'CCC'}]
        metadata=[{'total':3},[{'id':'AAA','region':{'id':'R1','value':'One'}},
            {'id':'BBB','region':{'id':'R1','value':'One'}},{'id':'CCC','region':{'id':'R2','value':'Two'}}]]
        self.assertEqual(list(region_samples(rows,metadata)),[('R1',[rows[2]]),('R2',rows[:2])])
        for bad in ([{'total':2},metadata[1][:2]], [{'total':4},metadata[1]+[metadata[1][0]]],
                    [{'total':3},[dict(metadata[1][0],region={'id':'NA','value':'Aggregates'})]+metadata[1][1:]]):
            with self.assertRaises(ValueError):list(region_samples(rows,bad))

if __name__=='__main__':unittest.main()
