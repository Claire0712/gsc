"""Apply frozen aggregation and gates without tuning on validation outcomes."""
import gzip,hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]/'downloads/reconstruction_pilot/multinetwork_validation'
protocol=json.loads((ROOT/'protocol.json').read_text())
expected=pd.date_range('2023-10-01','2023-12-01',freq='8h',inclusive='left',tz='UTC')
training=expected<pd.Timestamp('2023-11-01',tz='UTC');testing=~training
reports=[]
for cohort in protocol['cohorts']:
 asn=cohort['asn'];folder=ROOT/f'AS{asn}';rawfiles=sorted(folder.glob('msm*.json.gz'))
 if '--partial' in sys.argv and (len(rawfiles)!=4 or any(not f.with_suffix('.metadata.json').exists() for f in rawfiles)):
  reports.append({'asn':asn,'status':'download_pending'});continue
 assert len(rawfiles)==4,f'AS{asn}: incomplete download'
 rows=[]
 for f in rawfiles:
  for r in json.loads(gzip.decompress(f.read_bytes())):rows.append((r['timestamp'],r['prb_id'],r['msm_id'],r.get('sent',0),r.get('rcvd',0)))
 x=pd.DataFrame(rows,columns=['timestamp','probe','measurement','sent','received'])
 assert not x.duplicated(['timestamp','probe','measurement']).any()
 assert x.probe.isin(cohort['probe_ids']).all()
 x['bin']=pd.to_datetime(x.timestamp,unit='s',utc=True).dt.floor('8h')
 a=x.groupby(['bin','probe','measurement']).agg(sent=('sent','sum'),received=('received','sum'),records=('timestamp','size'))
 a['success']=(a.received/a.sent).where((a.sent>0)&(a.records>=protocol['min_reports_per_8h']))
 b=a.success.unstack('measurement').reindex(columns=protocol['measurements'])
 b['both_target_success']=b.mean(axis=1).where(b.notna().all(axis=1))
 g=b.both_target_success.groupby('bin').agg(['median','count']).reindex(expected)
 minimum=int(np.ceil(protocol['minimum_cohort_fraction']*len(cohort['probe_ids'])))
 proxy=g['median'].where(g['count']>=minimum)
 raw=json.loads(gzip.decompress((folder/'ioda_oct_nov.json.gz').read_bytes()))
 signals=[s for group in raw['data'] for s in group if s.get('datasource')=='ping-slash24' and str(s.get('entityCode'))==str(asn)]
 report={'asn':asn,'selection_country':cohort['country_for_selection'],'selected_probe_count':len(cohort['probe_ids']),'minimum_reporting_probe_count':minimum,'atlas_records':len(x),'not_country_data':True}
 if len(signals)!=1:
  report['status']='IODA target unavailable or ambiguous';reports.append(report);continue
 s=signals[0];assert s['step']==600
 y=pd.Series(s['values'],index=pd.to_datetime(s['from']+np.arange(len(s['values']))*600,unit='s',utc=True),dtype=float)
 counts=y.resample('8h').count();y=y.resample('8h').mean().where(counts>=protocol['min_ioda_reports_per_8h']).reindex(expected)
 baselines={'ioda':float(y[training].median()),'atlas':float(proxy[training].median())}
 report['baseline_values']={k:(v if np.isfinite(v) else None) for k,v in baselines.items()}
 if not all(np.isfinite(v) and v>0 for v in baselines.values()):
  report['status']='Invalid baseline';reports.append(report);continue
 target=y/baselines['ioda'];prediction=proxy/baselines['atlas']
 out=pd.DataFrame({'ioda_normalized':target,'atlas_proxy':prediction,'eligible_probes':g['count'],'ioda_reports':counts.reindex(expected),'validation':testing})
 out.to_csv(folder/'fixed_rule_comparison.csv',index_label='time_utc')
 a.to_csv(folder/'probe_target_8h.csv')
 t=target[testing];p=prediction[testing];good=t.notna()&p.notna();event=t<.8;detected=p<.8
 obs_deficit=float(np.maximum(0,1-t[good]).sum()*8);pred_deficit=float(np.maximum(0,1-p[good]).sum()*8)
 non_event=good & ~event
 m={'validation_bins':int(testing.sum()),'paired_bins':int(good.sum()),'paired_coverage':float(good.mean()),'baseline_proxy_coverage':float(proxy[training].notna().mean()),'mae':float(abs(t[good]-p[good]).mean()) if good.any() else None,'rmse':float(np.sqrt(((t[good]-p[good])**2).mean())) if good.any() else None,'observed_drop_bins':int(event.sum()),'detected_drop_bins':int((event&detected).sum()),'drop_bins_unscored':int((event&p.isna()).sum()),'drop_recall_all_observed':float((event&detected).sum()/event.sum()) if event.any() else None,'false_positive_bins':int((non_event&detected).sum()),'false_positive_fraction':float((non_event&detected).sum()/non_event.sum()) if non_event.any() else None,'paired_observed_deficit_hours':obs_deficit,'paired_proxy_deficit_hours':pred_deficit,'paired_deficit_relative_error':abs(pred_deficit-obs_deficit)/obs_deficit if obs_deficit>0 else None}
 baseline_mae=float(abs(t[good]-1).mean()) if good.any() else None
 m.update(constant_normal_baseline_mae=baseline_mae,mae_skill_vs_constant=(1-m['mae']/baseline_mae if baseline_mae is not None and baseline_mae>0 else None),target_standard_deviation=(float(t[good].std(ddof=0)) if good.any() else None),proxy_standard_deviation=(float(p[good].std(ddof=0)) if good.any() else None))
 gates={'coverage':m['paired_coverage']>=.8,'mae':m['mae'] is not None and m['mae']<=.05,'drop_recall':m['drop_recall_all_observed'] is not None and m['drop_recall_all_observed']>=.8,'false_positive_fraction':m['false_positive_fraction'] is not None and m['false_positive_fraction']<=.05,'deficit_relative_error':m['paired_deficit_relative_error'] is not None and m['paired_deficit_relative_error']<=.25}
 report.update(status='evaluated',event_validation_status=('tested' if m['observed_drop_bins'] else 'no_observed_outage'),deficit_note='Constant-median deficit diagnostic, not the proposal DHRD with its full baseline.',metrics=m,gates=gates,all_gates_passed=all(gates.values()),historical_backfill_approved=False)
 reports.append(report)
 print(json.dumps(report),flush=True)
summary={'protocol_sha256':hashlib.sha256((ROOT/'protocol.json').read_bytes()).hexdigest(),'networks':reports,'all_networks_passed':all(x.get('all_gates_passed',False) for x in reports),'historical_backfill_approved':False,'interpretation':'Independent ASN-level comparison in one month. Coverage-selected ASNs are not country-representative. No-event networks cannot validate outage recovery. Missing reports remain missing. No network telescope observations reconstructed.'}
(ROOT/('validation_partial.json' if '--partial' in sys.argv else 'validation.json')).write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
