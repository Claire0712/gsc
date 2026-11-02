"""Independent slot-loop risk and stable-confirmation reconstruction."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
p=Path(sys.argv[1]);m=json.loads((p/'manifest.json').read_text());rows=json.loads((p/'rows.json').read_text())
summary=json.loads((p/'summary.json').read_text())
threshold,slots=summary['maintenance_threshold'],summary['confirmation_slots']
assert (threshold,slots) in ((.9,24),(.98,24),(.95,12),(.95,36))
for name,e in list(m['inputs'].items())+[(str(p/n),e) for n,e in m['outputs'].items()]:
    raw=Path(name).read_bytes();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
for r in rows:
    point=next(Path(k) for k in m['inputs'] if k.endswith('/'+r['source_point_file']))
    with np.load(point,allow_pickle=False) as a:
        t=a['target_timestamps'];v=a['target_values'];b=a['baseline'];flags=a['target_exclusion_bits'];mask=a['analysis_available']
        start=r['metrics']['event_start'];end=r['metrics']['event_end_exclusive'];n=(end-start)//600
        np.testing.assert_array_equal(t,np.arange(start,end+259200,600))
        valid=np.isfinite(v)&(v>=0)&np.isfinite(b)&(b>0)&mask&((flags&30)==0)
        ratio=np.full(len(t),np.nan);ratio[valid]=v[valid]/b[valid];valid &= np.isfinite(ratio)
        assert r['metrics']['maintenance_threshold']==threshold and r['metrics']['confirmation_slots']==slots
        risk=bool(valid[:n].all() and ratio[n-1]<threshold);q=r['qualified'];assert q['risk_eligible']==risk;assert q['core_confounded_slots']==np.count_nonzero(flags[:n]&30)
        if not risk:continue
        length=0;status=None;cause=None
        for i in range(n,len(t)):
            if not valid[i]:
                time=(i-n)/6;status='missingness_censored';names=[name for bit,name in [(2,'stop_candidate'),(4,'cyclone_candidate'),(8,'uncertain_cyclone_edge'),(16,'unknown_mask_coverage')] if flags[i]&bit];cause=';'.join(names) if names else 'observation_or_reference_missing';break
            length=length+1 if ratio[i]>=threshold else 0
            if length==slots:time=(i-n+1)/6;status='confirmed';break
        if status is None:time=72;status='right_censored_72h'
        assert q['recovery']['status']==status and q['recovery']['followup_hours']==time
        assert q['censor_cause']==cause
for sig,s in json.loads((p/'summary.json').read_text())['signals'].items():
    rr=[r for r in rows if r['signal']==sig];qq=[r for r in rr if r['qualified']['risk_eligible']];pp=[r for r in qq if r['qualified']['recovery']['followup_hours']>0]
    assert s['technical_risk']==len(rr) and s['qualified_risk']==len(qq) and s['positive_followup']==len(pp)
    assert s['confirmed']==sum(r['qualified']['recovery']['status']=='confirmed' for r in pp)
print(json.dumps(dict(status='verified',risk_records=len(rows),manifest_sha256=hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest(),scope='Original slots, core mask and all first-stop/selected-run confirmation endpoints checked independently; no survival model or censoring ignorability claim.')))
