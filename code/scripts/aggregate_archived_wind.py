"""Reproduce existing0.1-degree weighted daily wind, no new downloads."""
import argparse,calendar,csv,json,time,zipfile
from datetime import date,timedelta
from pathlib import Path
import numpy as np
from scipy import sparse
from .run_connection_baseline import Sources

def match_days(previous,actual,limit):
    selected=actual[:limit] if limit else actual
    if previous is not None and previous!=selected:raise ValueError('U/V dates mismatch')
    return selected

def aggregate(weights,values):
    valid=np.isfinite(values);totals=np.asarray(weights.sum(axis=1)).ravel()
    mass=np.asarray(weights@valid.astype(float)).ravel()
    sums=np.asarray(weights@np.where(valid,values,0.)).ravel()
    means=np.divide(sums,mass,out=np.full_like(sums,np.nan),where=mass>0)
    support=np.divide(mass,totals,out=np.full_like(mass,np.nan),where=totals>0)
    return means,support

def run(args):
    import netCDF4
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources();wp=Path(args.weights);mp=Path(args.metadata)
    sources.verify(wp);metadata=json.loads(sources.read(mp));w=sparse.load_npz(wp)
    countries=metadata['countries'];grid=metadata['grid'];totals=np.asarray(w.sum(axis=1)).ravel()
    if w.shape!=(len(countries),grid['nlat']*grid['nlon']) or not w.has_canonical_format:raise ValueError('Weight shape/canonical mismatch')
    if not np.isfinite(w.data).all() or np.any(w.data<0):raise ValueError('Invalid population weight')
    if [c['index'] for c in countries]!=list(range(len(countries))) or len({c['boundary_code'] for c in countries})!=len(countries):raise ValueError('Country labels mismatch')
    np.testing.assert_allclose(totals,[c['population_assigned'] for c in countries],rtol=1e-10,atol=1e-6)
    np.testing.assert_allclose(totals.sum(),metadata['assigned_population'],rtol=1e-10,atol=1e-6)
    np.testing.assert_allclose(metadata['positive_population'],metadata['assigned_population']+metadata['unassigned_population'],rtol=1e-10,atol=1e-6)
    sources.verify(Path(__file__));out.mkdir(parents=True)
    def save(n,v):(out/n).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
    save('status.json',dict(status='running'));products={};months=[]
    try:
        for month in args.months:
            year,mm=int(month[:4]),int(month[4:]);first=date(year,mm,1)
            zp=Path(args.raw)/('weather_'+month[:4]+'_'+month[4:]+'.zip');sources.verify(zp)
            fields={};days=None
            for name,var in [('10m_u_component_of_wind_0_daily-mean.nc','u10'),('10m_v_component_of_wind_0_daily-mean.nc','v10')]:
                with zipfile.ZipFile(zp) as z:
                    if z.namelist().count(name)!=1:raise ValueError('Missing or duplicate wind member')
                    blob=z.read(name)
                with netCDF4.Dataset('memory.nc',memory=blob) as ds:
                    np.testing.assert_allclose(ds['latitude'][:],grid['latitude_start']+grid['latitude_step']*np.arange(grid['nlat']),atol=1e-7,rtol=0)
                    np.testing.assert_allclose(ds['longitude'][:],grid['longitude_start']+grid['longitude_step']*np.arange(grid['nlon']),atol=1e-7,rtol=0)
                    if ds[var].dimensions!=('valid_time','latitude','longitude') or ds[var].units!='m s**-1':raise ValueError('Wind field units/dimensions mismatch')
                    dt=netCDF4.num2date(ds['valid_time'][:],ds['valid_time'].units)
                    expected=[first+timedelta(days=k) for k in range(calendar.monthrange(year,mm)[1])]
                    actual=[date(d.year,d.month,d.day) for d in dt]
                    if actual!=expected or any(d.hour or d.minute or d.second for d in dt):raise ValueError('Noncomplete UTC daily axis')
                    days=match_days(days,actual,args.limit_days)
                    vals=[]
                    for i,day in enumerate(days):
                        field=np.asarray(np.ma.filled(ds[var][i,:,:],np.nan),dtype=float).ravel()
                        means,support=aggregate(w,field);vals.append((means,support))
                    fields[var]=vals
                del blob
            filename='wind_'+month+'.csv'
            with (out/filename).open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['boundary_code','iso3','date','variable','statistic','value','valid_population_fraction','population_assigned','unit','weight_year','day_definition']);writer.writeheader()
                for var in ('u10','v10'):
                    for day,(means,support) in zip(days,fields[var]):
                        for c,v,p,t in zip(countries,means,support,totals):
                            writer.writerow(dict(boundary_code=c['boundary_code'],iso3=c.get('iso3') or '',date=str(day),variable=var,statistic='daily_mean',value=float(v) if np.isfinite(v) else '',valid_population_fraction=float(p) if np.isfinite(p) else '',population_assigned=float(t),unit='m s**-1',weight_year=2025,day_definition='UTC'))
            products[filename]=Sources().verify(out/filename);months.append(dict(month=month,days=len(days)))
            save('status.json',dict(status='running',completed_months=months))
        sources.check();save('summary.json',dict(months=months,countries=len(countries),elapsed_seconds=time.monotonic()-start,
            scope='Existing archived daily-mean U/V only. Original mass weights retained, no renormalization of missing population into full-country claim. Finite-support means with coverage. Structural/row/global metadata mass checks and exact grid/time checks passed, not a fresh native-population/boundary reassignment certification. Wind vector not gust; no inference.'))
        products['summary.json']=Sources().verify(out/'summary.json');save('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products));save('status.json',dict(status='completed'));print((out/'summary.json').read_text())
    except BaseException as e:save('status.json',dict(status='failed',error=str(e)));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('weights','metadata','raw','output'):p.add_argument('--'+n,required=True)
    p.add_argument('--months',nargs='+',required=True);p.add_argument('--limit-days',type=int,default=0);run(p.parse_args())
