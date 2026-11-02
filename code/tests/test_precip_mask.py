import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import h5netcdf
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


class MaskTests(unittest.TestCase):
    def load(self):
        path=ROOT/'scripts/audit_precip_mask.py'
        self.assertTrue(path.exists(),'mask auditor missing')
        spec=importlib.util.spec_from_file_location('mask_audit',path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

    def fixture(self,root,bad_time=False,bad_grid=False):
        path=Path(root)/'precip_2018_01.nc'
        with h5netcdf.File(path,'w') as f:
            f.dimensions={'valid_time':31,'latitude':2,'longitude':3}
            t=f.create_variable('valid_time',('valid_time',),dtype='i8')
            t[:]=1514764800+np.arange(31)*86400+(600 if bad_time else 0)
            t.attrs.update(units='seconds since 1970-01-01',calendar='proleptic_gregorian')
            lat=f.create_variable('latitude',('latitude',),dtype='f8');lat[:]=[90,89.8 if bad_grid else 89.9]
            lon=f.create_variable('longitude',('longitude',),dtype='f8');lon[:]=[0,.1,.2]
            tp=f.create_variable('tp',('valid_time','latitude','longitude'),dtype='f4',fillvalue=np.nan)
            values=np.ones((31,2,3),dtype='f4');values[:,0,0]=np.nan;values[0,1,0]=0
            values[1,0,0]=1;values[1,0,1]=np.nan;values[2,0,0]=np.inf
            tp[:]=values;tp.attrs.update(units='m',GRIB_stepType='accum',GRIB_dataType='fc')
        return path,hashlib.sha256(path.read_bytes()).hexdigest(),(np.array([90,89.9]),np.array([0,.1,.2]))

    def test_mask_swap_detected_even_with_same_count_and_dates(self):
        m=self.load()
        with tempfile.TemporaryDirectory() as temp:
            path,sha,grid=self.fixture(temp)
            r=m.audit_month(path,sha,grid=grid)
            self.assertEqual(r['days'],31)
            self.assertFalse(r['all_masks_equal_to_first'])
            self.assertEqual(r['daily'][1]['different_cells_from_first'],2)
            self.assertEqual(r['daily'][0]['finite_cells'],5)
            self.assertEqual(r['daily'][2]['infinity_cells'],1)
            self.assertEqual(r['daily'][2]['different_cells_from_first'],0)
            self.assertEqual(r['daily'][0]['precipitation_day'],'2017-12-31')
            self.assertEqual(r['daily'][-1]['precipitation_day'],'2018-01-30')
            self.assertFalse(r['daily'][0]['in_analysis_weather_period'])
            expected=hashlib.sha256(np.packbits([0,1,1,1,1,1],bitorder='big').tobytes()).hexdigest()
            self.assertEqual(r['daily'][0]['finite_mask_sha256'],expected)
            self.assertFalse(r['full_period_certified'])

    def test_input_identity_grid_time_and_output_reuse_rejected(self):
        m=self.load()
        for case in ['time','grid','hash']:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
                path,sha,grid=self.fixture(temp,bad_time=case=='time',bad_grid=case=='grid')
                with self.assertRaises(ValueError):m.audit_month(path,'0'*64 if case=='hash' else sha,grid=grid)
        with tempfile.TemporaryDirectory() as temp:
            path,sha,grid=self.fixture(temp);out=Path(temp)/'result'
            r=m.run(path,out,sha,grid=grid,latitude_rows=1)
            self.assertEqual(r['rows_read'],1)
            self.assertEqual(r['spatial_scope'],'first_latitude_rows_only')
            self.assertEqual(r['daily'][0]['finite_cells'],2)
            self.assertTrue((out/'manifest.json').is_file())
            with self.assertRaises(FileExistsError):m.run(path,out,sha,grid=grid)
        result=subprocess.run([sys.executable,'-W','error',str(ROOT/'scripts/audit_precip_mask.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_fixed_width_byte_attributes_match_real_netcdf(self):
        m=self.load()
        with tempfile.TemporaryDirectory() as temp:
            path,sha,grid=self.fixture(temp)
            with h5netcdf.File(path,'a') as f:
                for variable,attrs in [('tp',{'units':'m','GRIB_stepType':'accum','GRIB_dataType':'fc'}),
                                       ('valid_time',{'units':'seconds since 1970-01-01','calendar':'proleptic_gregorian'})]:
                    for key,value in attrs.items():f[variable].attrs[key]=np.bytes_(value)
            sha=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(m.audit_month(path,sha,grid=grid)['days'],31)


if __name__=='__main__':unittest.main()
