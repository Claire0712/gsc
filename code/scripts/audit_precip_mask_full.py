"""All existing97precipitation files: finite-mask/date QA, never rainfall means."""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import sys
import time
import h5netcdf
import numpy as np
if __package__:
    from . import audit_precip_mask as single
    from . import audit_precip_values as previous
else:
    import audit_precip_mask as single
    import audit_precip_values as previous

PILOT_NAMES=['precip_2018_01.nc','precip_2026_01.nc']


def audit_dates(times,*,pilot):
    names=PILOT_NAMES if pilot else previous.expected_names()
    expected=np.concatenate([previous.expected_times(n) for n in names]).tolist()
    if len(times)!=len(set(times)):raise ValueError('Duplicate source dates')
    if times!=expected:raise ValueError('Missing, extra or unordered source dates')
    days=[(datetime.fromtimestamp(t,timezone.utc)-timedelta(days=1)).date().isoformat() for t in times]
    target=[d for d in days if '2018-01-01'<=d<='2025-12-31']
    if not pilot and (len(target)!=2922 or target[0]!='2018-01-01' or target[-1]!='2025-12-31'):
        raise ValueError('Incomplete target precipitation-day coverage')
    return dict(source_day_count=len(times),source_duplicate_days=0,target_day_count=len(target),
                missing_expected_source_days=[],out_of_range_precipitation_days=[d for d in days if d not in target],
                first_precipitation_day=days[0],last_precipitation_day=days[-1],
                full_target_date_coverage=not pilot)


def scan_file(path,first,grid,progress):
    times=previous.expected_times(path.name);nlat,nlon=map(len,grid);daily=[]
    with h5netcdf.File(path,'r',rdcc_nbytes=single.CACHE_BYTES) as f:
        for name in ['tp','valid_time','latitude','longitude']:
            if name not in f.variables:raise ValueError('Missing variable '+name)
        v=f['tp']
        if v.dimensions!=('valid_time','latitude','longitude') or v.shape!=(len(times),nlat,nlon) or v.dtype.kind not in 'fi':
            raise ValueError('Invalid tp schema: '+path.name)
        for name,allowed in [('units',('m',)),('GRIB_stepType',('accum',)),('GRIB_dataType',('fc',))]:
            if single.attribute(v,name) not in allowed:raise ValueError('Invalid tp '+name)
        if 'scale_factor' in v.attrs or 'add_offset' in v.attrs:raise ValueError('Unexpected packed values')
        if '_FillValue' in v.attrs:
            fill=np.asarray(v.attrs['_FillValue'])
            if fill.size!=1 or not np.isnan(fill).all():raise ValueError('Fill must be NaN')
        for name,expected in zip(['latitude','longitude'],grid):
            c=f[name]
            if c.dimensions!=(name,) or c.shape!=(len(expected),) or not np.allclose(c[:],expected,rtol=0,atol=1e-5):
                raise ValueError('Unexpected spatial coordinate '+name)
        t=f['valid_time']
        if t.dimensions!=('valid_time',) or t.shape!=times.shape or not np.array_equal(t[:],times):raise ValueError('Unexpected source timestamps')
        if single.attribute(t,'units') not in ['seconds since 1970-01-01','seconds since 1970-01-01 00:00:00','seconds since 1970-01-01T00:00:00']:
            raise ValueError('Unexpected time units')
        if single.attribute(t,'calendar') not in ['gregorian','proleptic_gregorian','standard']:raise ValueError('Unexpected calendar')
        for i,seconds in enumerate(times):
            values=v[i,:,:];finite=np.isfinite(values)
            if first is None:first=finite.copy()
            source_time=datetime.fromtimestamp(int(seconds),timezone.utc)
            day=(source_time-timedelta(days=1)).date().isoformat()
            daily.append(dict(source_utc=source_time.isoformat().replace('+00:00','Z'),precipitation_day=day,
                              in_analysis_weather_period='2018-01-01'<=day<='2025-12-31',cells=values.size,
                              finite_cells=int(finite.sum()),nan_cells=int(np.isnan(values).sum()),infinity_cells=int(np.isinf(values).sum()),
                              different_cells_from_global_first=int(np.count_nonzero(finite!=first)),
                              finite_mask_sha256=hashlib.sha256(np.packbits(finite.ravel(order='C'),bitorder='big').tobytes()).hexdigest()))
            progress(i+1,daily[-1]['source_utc'])
    return daily,first,times.tolist()


def run(source_directory,source_manifest,output,*,pilot=False,grid=None):
    source_directory=Path(source_directory).resolve();source_manifest=Path(source_manifest).resolve();output=Path(output).absolute()
    if output.exists():raise FileExistsError(output)
    if source_directory==output.resolve() or source_directory in output.resolve().parents or output.resolve() in source_directory.parents:
        raise ValueError('Input/output directory overlap')
    if output.resolve() in source_manifest.parents:raise ValueError('Output overlaps provenance')
    if grid is None:grid=(90-np.arange(1801)/10,np.arange(3600)/10)
    started=time.monotonic();names=PILOT_NAMES if pilot else previous.expected_names()
    output.mkdir(parents=True,exist_ok=False)
    state=dict(status='running',pid=os.getpid(),pilot=pilot,started_utc=previous.utc_now(),files_expected=len(names),
               days_expected=sum(len(previous.expected_times(n)) for n in names),files_completed=0,days_completed=0,
               full_period_certified=False,population_weights_certified=False,country_precipitation_computed=False)
    def publish(name,value):previous.atomic_json(output/name,value)
    def status(**changes):state.update(changes,updated_utc=previous.utc_now());publish('status.json',state)
    status(phase='validate_manifest')
    try:
        manifest_stamp=single.stamp(source_manifest);manifest_sha=single.sha256(source_manifest)
        input_manifest=json.loads(source_manifest.read_text())
        status_path=source_manifest.parent/'status.json'
        status_stamp=single.stamp(status_path)
        if json.loads(status_path.read_text()).get('status')!='completed':raise ValueError('Original value audit must be completed')
        expected={}
        for entry in input_manifest['sources']:
            name=Path(entry['path']).name
            if name in expected or not re.fullmatch('[a-f0-9]{64}',str(entry.get('sha256',''))) or not isinstance(entry.get('bytes'),int) or entry['bytes']<0:
                raise ValueError('Invalid/duplicate source manifest entry')
            expected[name]=entry
        if set(expected)!=set(previous.expected_names()):raise ValueError('Manifest must have exact97source files')
        if not pilot and {p.name for p in source_directory.glob('precip_*.nc')}!=set(expected):raise ValueError('Source directory inventory differs from97file manifest')
        (output/'monthly').mkdir()
        inputs={};stamps={};all_times=[];first=None;records=[];changed=0;mask_hashes=set()
        for name in names:
            path=source_directory/name;initial=single.stamp(path)
            status(phase='hash_source',current_file=name,current_file_days_completed=0)
            digest=single.sha256(path)
            if digest!=expected[name]['sha256'] or initial[2]!=expected[name]['bytes']:raise ValueError('Source SHA256/size mismatch: '+name)
            if single.stamp(path)!=initial:raise ValueError('Source changed while hashing')
            inputs[name]=dict(path=str(path),sha256=digest,bytes=initial[2]);stamps[path]=initial
            completed=state['days_completed']
            def progress(count,utc):status(phase='compare_masks',current_file_days_completed=count,days_completed=completed+count,current_source_utc=utc)
            daily,first,times=scan_file(path,first,grid,progress)
            if single.stamp(path)!=initial:raise ValueError('Source changed during scan')
            all_times.extend(times);changed+=sum(r['different_cells_from_global_first']>0 for r in daily)
            mask_hashes.update(r['finite_mask_sha256'] for r in daily)
            monthly=dict(file=name,source_sha256=digest,days=len(daily),daily=daily,
                         global_reference_source_utc='2018-01-01T00:00:00Z',full_period_certified=False)
            monthly_path='monthly/'+path.stem+'.json';publish(monthly_path,monthly)
            records.append(dict(file=monthly_path,sha256=single.sha256(output/monthly_path),bytes=(output/monthly_path).stat().st_size))
            status(files_completed=state['files_completed']+1)
        dates=audit_dates(all_times,pilot=pilot)
        if any(single.stamp(path)!=initial for path,initial in stamps.items()):raise ValueError('Source changed before completion')
        if single.stamp(source_manifest)!=manifest_stamp or single.stamp(status_path)!=status_stamp:raise ValueError('Audit provenance changed')
        if not pilot and {p.name for p in source_directory.glob('precip_*.nc')}!=set(expected):raise ValueError('Source inventory changed')
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        summary=dict(status='completed',pilot=pilot,files=len(names),days=len(all_times),date_audit=dates,
                     changed_source_days=changed,all_masks_equal_to_global_first=changed==0,finite_mask_unique_hashes=len(mask_hashes),
                     global_reference_source_utc='2018-01-01T00:00:00Z',global_reference_mask_sha256=hashlib.sha256(np.packbits(first.ravel(order='C'),bitorder='big').tobytes()).hexdigest(),
                     mask_encoding='isfinite; C-order latitude-major flatten; np.packbits bitorder=big; trailing padding zero',
                     grid_shape=[len(x) for x in grid],full_period_certified=not pilot,population_weights_certified=False,
                     country_precipitation_computed=False,coverage_threshold_changed=False,hdf5_cache_bytes=single.CACHE_BYTES,
                     elapsed_seconds=time.monotonic()-started,peak_rss_bytes=int(rss if sys.platform=='darwin' else rss*1024),finished_utc=previous.utc_now(),
                     interpretation='Certification scope is source finite-mask/time audit only; spatial constancy is separately reported. No population weight certification or rainfall control eligibility.',
                     command=sys.argv)
        publish('summary.json',summary)
        records.append(dict(file='summary.json',sha256=single.sha256(output/'summary.json'),bytes=(output/'summary.json').stat().st_size))
        scripts={str(Path(m).resolve()):single.sha256(m) for m in [__file__,single.__file__,previous.__file__]}
        publish('manifest.json',dict(status='completed',source_audit_manifest=dict(path=str(source_manifest),sha256=manifest_sha),
                                    sources=inputs,outputs=records,scripts=scripts,numpy_version=np.__version__,h5netcdf_version=h5netcdf.__version__))
        status(status='completed',phase='completed',full_period_certified=not pilot,elapsed_seconds=summary['elapsed_seconds'])
        return summary
    except BaseException as exc:
        status(status='failed',phase='failed',error=repr(exc));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-directory',required=True,type=Path);p.add_argument('--source-manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--pilot',action='store_true')
    a=p.parse_args();print(json.dumps(run(a.source_directory,a.source_manifest,a.output,pilot=a.pilot)))
