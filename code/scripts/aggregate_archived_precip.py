"""Archived native-grid precipitation finite-population means, not full-population means."""
import argparse,csv,json,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
from scipy import sparse
from .aggregate_archived_wind import aggregate
from .run_connection_baseline import Sources
from .audit_precip_values import expected_times


def precip_statistics(weights,values):
    means,support=aggregate(weights,values)
    return means*1000.,support


def accumulation_date(seconds):
    if seconds%86400:raise ValueError('Accumulation label must be UTC midnight')
    return str((datetime.fromtimestamp(seconds,timezone.utc)-timedelta(days=1)).date())


def validate_units(value):
    if isinstance(value,bytes):value=value.decode('ascii')
    if value!='m':raise ValueError('Precipitation source units must be metres')


def run(args):
    import h5netcdf
    start=time.monotonic();out=Path(args.output)
    if out.exists():raise FileExistsError(out)
    sources=Sources()
    wp=Path(args.weights);mp=Path(args.metadata);receipt=Path(args.weight_receipt)
    certificate=json.loads(sources.read(receipt));assert certificate['status']=='verified'
    for p,sha in certificate['sources'].items():
        if sources.verify(Path(p))['sha256']!=sha:raise ValueError('Weight certificate source changed')
    metadata=json.loads(sources.read(mp));sources.verify(wp)
    weights=sparse.load_npz(wp).tocsr();countries=metadata['countries']
    assert weights.shape==(len(countries),1801*3600)
    assert [r['index'] for r in countries]==list(range(len(countries)))
    assert len({r['boundary_code'] for r in countries})==len(countries)
    assert weights.has_canonical_format and np.isfinite(weights.data).all() and (weights.data>=0).all()
    totals=np.asarray(weights.sum(axis=1)).ravel()
    np.testing.assert_allclose(totals,[r['population_assigned'] for r in countries],rtol=1e-10,atol=1e-6)
    audit=json.loads(sources.read(Path(args.audit_manifest)))
    sources.verify(Path(__file__));sources.verify(Path(__file__).with_name('aggregate_archived_wind.py'))
    out.mkdir(parents=True);products={};completed=[]
    def save(name,value):(out/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    save('status.json',dict(status='running'))
    try:
        for month in args.months:
            name='precip_'+month[:4]+'_'+month[4:]+'.nc';path=Path(args.raw)/name
            fingerprint=sources.verify(path)
            assert fingerprint['sha256']==audit['sources'][name]['sha256']
            times=expected_times(name)
            if args.limit_days:times=times[:args.limit_days]
            filename='precip_'+month+'.csv'
            with h5netcdf.File(path,'r',rdcc_nbytes=8*1024*1024) as source,(out/filename).open('w',newline='') as f:
                np.testing.assert_allclose(source['latitude'][:],90.-np.arange(1801)/10.,rtol=0,atol=1e-7)
                np.testing.assert_allclose(source['longitude'][:],np.arange(3600)/10.,rtol=0,atol=1e-7)
                assert source['tp'].dimensions==('valid_time','latitude','longitude')
                validate_units(source['tp'].attrs['units'])
                np.testing.assert_array_equal(source['valid_time'][:len(times)],times)
                writer=csv.DictWriter(f,fieldnames=['boundary_code','date','valid_time','value_mm','valid_population_fraction','population_assigned','day_definition'])
                writer.writeheader()
                for i,seconds in enumerate(times):
                    values=np.asarray(source['tp'][i,:,:],dtype=float).ravel()
                    means,support=precip_statistics(weights,values)
                    for country,v,p,t in zip(countries,means,support,totals):
                        writer.writerow(dict(boundary_code=country['boundary_code'],date=accumulation_date(int(seconds)),valid_time=int(seconds),value_mm=float(v) if np.isfinite(v) else '',valid_population_fraction=float(p) if np.isfinite(p) else '',population_assigned=float(t),day_definition='UTC accumulation ending at next midnight'))
            products[filename]=Sources().verify(out/filename);completed.append(dict(month=month,days=len(times)))
            save('status.json',dict(status='running',completed_months=completed))
        sources.check()
        save('summary.json',dict(months=completed,countries=len(countries),elapsed_seconds=time.monotonic()-start,scope='Finite-population-supported daily accumulation mean in mm; source valid_time minus one day. Missing cells remain missing; support fraction reported. No model fitting or full-country-mean claim.'))
        products['summary.json']=Sources().verify(out/'summary.json')
        save('manifest.json',dict(status='completed',inputs=sources.entries,outputs=products))
        save('status.json',dict(status='completed'))
        print((out/'summary.json').read_text())
    except BaseException as error:
        save('status.json',dict(status='failed',error=str(error)));raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('weights','metadata','weight-receipt','raw','output','audit-manifest'):p.add_argument('--'+name,required=True)
    p.add_argument('--months',nargs='+',required=True);p.add_argument('--limit-days',type=int,default=0)
    run(p.parse_args())
