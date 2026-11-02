"""January 2018 finite-mask QA only; no rainfall values or population eligibility."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import h5netcdf
import numpy as np

CACHE_BYTES=256*1024*1024


def attribute(variable,name):
    value=variable.attrs.get(name)
    return value.decode('utf-8') if isinstance(value,bytes) else value


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def stamp(path):
    s=Path(path).stat()
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def audit_month(source,expected_sha256,*,latitude_rows=None,grid=None):
    """Stream one slice, compare every finite mask to day 1; grid is fixture-only."""
    source=Path(source)
    if source.name!='precip_2018_01.nc':raise ValueError('Only January 2018 is authorized')
    initial=stamp(source)
    if sha256(source)!=expected_sha256:raise ValueError('Source SHA256 mismatch')
    if grid is None:grid=(90-np.arange(1801)/10,np.arange(3600)/10)
    nlat,nlon=(len(x) for x in grid)
    rows=nlat if latitude_rows is None else latitude_rows
    if isinstance(rows,bool) or not isinstance(rows,int) or not 1<=rows<=nlat:raise ValueError('Invalid latitude row limit')
    times=1514764800+np.arange(31,dtype=np.int64)*86400
    started=time.monotonic();daily=[];first=None
    with h5netcdf.File(source,'r',rdcc_nbytes=CACHE_BYTES) as f:
        for name in ['tp','valid_time','latitude','longitude']:
            if name not in f.variables:raise ValueError('Missing variable '+name)
        v=f['tp']
        if v.dimensions!=('valid_time','latitude','longitude') or v.shape!=(31,nlat,nlon) or v.dtype.kind not in 'fi':
            raise ValueError('Invalid tp schema')
        for name,allowed in [('units',('m',)),('GRIB_stepType',('accum',)),('GRIB_dataType',('fc',))]:
            if attribute(v,name) not in allowed:raise ValueError('Invalid tp '+name)
        if 'scale_factor' in v.attrs or 'add_offset' in v.attrs:raise ValueError('Unexpected packed values')
        if '_FillValue' in v.attrs:
            fill=np.asarray(v.attrs['_FillValue'])
            if fill.size!=1 or not np.isnan(fill).all():raise ValueError('Fill must be NaN')
        for name,expected in zip(['latitude','longitude'],grid):
            c=f[name]
            if c.dimensions!=(name,) or c.shape!=(len(expected),) or not np.allclose(c[:],expected,rtol=0,atol=1e-5):
                raise ValueError('Unexpected spatial coordinate '+name)
        t=f['valid_time']
        if t.dimensions!=('valid_time',) or t.shape!=(31,) or not np.array_equal(t[:],times):raise ValueError('Unexpected January timestamps')
        if attribute(t,'units') not in ['seconds since 1970-01-01','seconds since 1970-01-01 00:00:00','seconds since 1970-01-01T00:00:00']:
            raise ValueError('Unexpected time units')
        if attribute(t,'calendar') not in ['gregorian','proleptic_gregorian','standard']:raise ValueError('Unexpected calendar')
        chunks=list(v.chunks) if v.chunks else None
        for i,seconds in enumerate(times):
            values=v[i,:rows,:]
            finite=np.isfinite(values)
            if first is None:first=finite.copy()
            packed=np.packbits(finite.ravel(order='C'),bitorder='big').tobytes()
            dt=datetime.fromtimestamp(int(seconds),timezone.utc)
            day=(dt-timedelta(days=1)).date().isoformat()
            daily.append(dict(source_utc=dt.isoformat().replace('+00:00','Z'),precipitation_day=day,
                              in_analysis_weather_period='2018-01-01'<=day<='2025-12-31',cells=values.size,
                              finite_cells=int(finite.sum()),nan_cells=int(np.isnan(values).sum()),
                              infinity_cells=int(np.isinf(values).sum()),different_cells_from_first=int(np.count_nonzero(finite!=first)),
                              finite_mask_sha256=hashlib.sha256(packed).hexdigest()))
    if stamp(source)!=initial or sha256(source)!=expected_sha256 or stamp(source)!=initial:
        raise ValueError('Source changed during audit')
    return dict(status='completed',source_path=str(source.resolve()),source_sha256=expected_sha256,source_bytes=initial[2],
                days=31,grid_shape=[nlat,nlon],rows_read=rows,spatial_scope='full_source_grid' if rows==nlat else 'first_latitude_rows_only',
                spatial_latitude_range=[float(grid[0][0]),float(grid[0][rows-1])],
                mask_encoding='isfinite; C-order latitude-major flatten; np.packbits bitorder=big; trailing padding zero',
                first_mask_sha256=daily[0]['finite_mask_sha256'],all_masks_equal_to_first=all(r['different_cells_from_first']==0 for r in daily),
                changed_source_days=sum(r['different_cells_from_first']>0 for r in daily),
                finite_mask_unique_hashes=len({r['finite_mask_sha256'] for r in daily}),
                daily=daily,hdf5_cache_bytes=CACHE_BYTES,source_chunk_shape=chunks,scan_and_rehash_seconds=time.monotonic()-started,
                full_period_certified=False,population_weights_certified=False,country_precipitation_computed=False,
                coverage_threshold_changed=False,limitations=['January 2018 source timestamps only; not full-period mask certification.',
                'No population support or rainfall averages computed.','Source Jan1 labels precipitation Dec31 2017; source Jan31 labels Jan30 2018.'])


def run(source,output,expected_sha256,*,latitude_rows=None,grid=None):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    source=Path(source).resolve()
    if output.resolve()==source or output.resolve() in source.parents:raise ValueError('Output overlaps input')
    start=time.monotonic()
    result=audit_month(source,expected_sha256,latitude_rows=latitude_rows,grid=grid)
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result.update(finished_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start,
                  peak_rss_bytes=int(rss if sys.platform=='darwin' else rss*1024),script_sha256=sha256(__file__),
                  command=sys.argv,numpy_version=np.__version__,h5netcdf_version=h5netcdf.__version__)
    output.mkdir(parents=True,exist_ok=False)
    with (output/'summary.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    manifest=dict(status='completed',outputs={'summary.json':dict(sha256=sha256(output/'summary.json'),bytes=(output/'summary.json').stat().st_size)})
    with (output/'manifest.json').open('x') as f:json.dump(manifest,f,indent=2)
    with (output/'status.json').open('x') as f:json.dump(dict(status='completed',full_period_certified=False),f)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--source-sha256',required=True);p.add_argument('--latitude-rows',type=int)
    a=p.parse_args();result=run(a.source,a.output,a.source_sha256,latitude_rows=a.latitude_rows)
    print(json.dumps({k:v for k,v in result.items() if k!='daily'}))
