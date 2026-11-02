import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import h5netcdf
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import audit_precip_values as previous


class FullMaskTests(unittest.TestCase):
    def load(self):
        path=ROOT/'scripts/audit_precip_mask_full.py'
        self.assertTrue(path.exists(),'full mask auditor missing')
        spec=importlib.util.spec_from_file_location('fullmask',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

    def fixture(self,temp,swap=True):
        root=Path(temp);source=root/'source';source.mkdir();rows=[]
        for name in previous.expected_names():
            path=source/name
            if name in ['precip_2018_01.nc','precip_2026_01.nc']:
                times=previous.expected_times(name)
                with h5netcdf.File(path,'w') as f:
                    f.dimensions={'valid_time':len(times),'latitude':2,'longitude':3}
                    t=f.create_variable('valid_time',('valid_time',),dtype='i8');t[:]=times
                    t.attrs.update(units=np.bytes_('seconds since 1970-01-01'),calendar=np.bytes_('gregorian'))
                    lat=f.create_variable('latitude',('latitude',),dtype='f8');lat[:]=[90,89.9]
                    lon=f.create_variable('longitude',('longitude',),dtype='f8');lon[:]=[0,.1,.2]
                    v=f.create_variable('tp',('valid_time','latitude','longitude'),dtype='f4',fillvalue=np.nan)
                    x=np.ones((len(times),2,3),dtype='f4');x[:,0,0]=np.nan;x[:,1,1]=0
                    if name=='precip_2026_01.nc' and swap:x[:,0,0]=1;x[:,0,1]=np.nan
                    v[:]=x;v.attrs.update(units=np.bytes_('m'),GRIB_stepType=np.bytes_('accum'),GRIB_dataType=np.bytes_('fc'))
                data=path.read_bytes();sha=hashlib.sha256(data).hexdigest();size=len(data)
            else:sha='0'*64;size=0
            rows.append(dict(path='/old/source/'+name,sha256=sha,bytes=size))
        manifest=root/'manifest.json';manifest.write_text(json.dumps(dict(sources=rows)))
        (root/'status.json').write_text('{"status":"completed"}')
        return source,manifest,(np.array([90,89.9]),np.array([0,.1,.2]))

    def test_global_first_mask_not_reset_at_boundary_and_scope(self):
        m=self.load()
        with tempfile.TemporaryDirectory() as temp:
            source,manifest,grid=self.fixture(temp)
            output=Path(temp)/'out';result=m.run(source,manifest,output,pilot=True,grid=grid)
            self.assertEqual(result['days'],32)
            self.assertEqual(result['changed_source_days'],1)
            self.assertFalse(result['full_period_certified'])
            self.assertFalse(result['population_weights_certified'])
            boundary=json.loads((output/'monthly/precip_2026_01.json').read_text())['daily'][0]
            self.assertEqual(boundary['different_cells_from_global_first'],2)
            self.assertEqual(boundary['precipitation_day'],'2025-12-31')
            self.assertEqual(boundary['finite_cells'],5)
            self.assertEqual(json.loads((output/'status.json').read_text())['status'],'completed')
            with self.assertRaises(FileExistsError):m.run(source,manifest,output,pilot=True,grid=grid)

    def test_full_date_accounting_duplicates_and_missing(self):
        m=self.load()
        times=np.concatenate([previous.expected_times(n) for n in previous.expected_names()]).tolist()
        result=m.audit_dates(times,pilot=False)
        self.assertEqual(result['target_day_count'],2922)
        self.assertEqual(result['out_of_range_precipitation_days'],['2017-12-31'])
        for bad in [times+times[-1:],times[:-1],times[1:]]:
            with self.assertRaises(ValueError):m.audit_dates(bad,pilot=False)

    def test_bad_manifest_hash_and_source_change_fail_closed(self):
        m=self.load()
        for case in ['manifest','hash']:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
                source,manifest,grid=self.fixture(temp)
                if case=='manifest':
                    content=json.loads(manifest.read_text());content['sources']=content['sources'][:-1];manifest.write_text(json.dumps(content))
                else:
                    with (source/'precip_2018_01.nc').open('ab') as f:f.write(b'corrupt')
                with self.assertRaises(ValueError):m.run(source,manifest,Path(temp)/'out',pilot=True,grid=grid)


if __name__=='__main__':unittest.main()
