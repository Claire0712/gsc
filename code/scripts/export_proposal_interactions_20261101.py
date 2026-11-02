"""Publish every limited-interaction outcome and original full-window peaks."""
from pathlib import Path
import json,csv,hashlib
import numpy as np
from docx import Document
from docx.shared import Inches,Pt,RGBColor
root=Path(__file__).resolve().parents[1];p=root/'analysis/2026-11-01_proposal_interactions/v1/full_outputs';out=root/'deliverables/2026-11-01_proposal_interactions_v2';assert not out.exists();m=json.loads((p/'manifest.json').read_text());v=json.loads((p.parent/'full_outputs.verify.json').read_text());h=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();assert v['status']=='verified' and v['manifest_sha256']==h(p/'manifest.json')
for f,meta in m['outputs'].items():assert h(p/f)==meta['sha256']
models=json.loads((p/'results.json').read_text());rows=[];labels={'ping-slash24':'AP','bgp':'BGP','merit-nt':'Telescope'}
for r in models:
 for outcome,f in r['results'].items():
  ok=f['estimable'];rows.append(dict(signal=labels[r['signal']],kind=r['kind'],outcome=outcome,n=f['n'],countries=f['countries'],estimable=ok,reason=f.get('reason'),beta=f['beta'][-1] if ok else None,interval95_normal_cr0=f['interval95_normal'][-1] if ok else None,p_normal_cr0=f['interaction_p_normal_cr0'],bh=f['interaction_bh'],by=f['interaction_by'],heat_mean=r['centering']['heat_mean'],modifier_mean=r['centering']['modifier_mean'],base_rss=f['base_rss'],rss=f.get('rss'),partial_residual_variance_explained=f['partial_residual_variance_explained'],predicted_outside_unit_interval=f.get('predicted_outside_unit_interval')))
assert len(rows)==30 and sum(r['estimable'] for r in rows)==20
metricsfile=root/'analysis/2026-10-12_resilience_metrics/v1/full_outputs/event_metrics.json';metrics=json.loads(metricsfile.read_text());peaks=[]
for sig,label in labels.items():
 rr=[r for r in metrics if r['signal']==sig and r['full_observed_unconfounded'] and r['metrics']['full_window_complete']];x=np.array([r['metrics']['peak_loss_full'] for r in rr]);q=np.quantile(x,[.25,.5,.75]);peaks.append(dict(signal=label,n=len(rr),countries=len({r['country_id'] for r in rr}),q25=float(q[0]),median=float(q[1]),q75=float(q[2])))
out.mkdir();obj=dict(models=models,focal_interactions=rows,full_window_peak_loss=peaks,source_sha256={str(f.relative_to(root)):h(f) for f in (p/'manifest.json',p/'results.json',p.parent/'full_outputs.verify.json',metricsfile)},scope='Post-hoc completion of existing proposal 9.3. Separate 30-case within-family normal-CR0 BH/BY; no study-wide multiplicity certification. Full peaks are unchanged original descriptive metrics.');(out/'source.json').write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
for name,rr in [('all_30_interactions',rows),('full_window_peak_loss',peaks)]:
 with (out/(name+'.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows([{k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rr])
d=Document();s=d.sections[0];s.top_margin=s.bottom_margin=Inches(.7);s.left_margin=s.right_margin=Inches(.65)
for n in ('Normal','Title','Heading 1','Heading 2'):d.styles[n].font.name='Arial';d.styles[n].font.color.rgb=RGBColor(0,0,0)
d.styles['Normal'].font.size=Pt(9);d.styles['Title'].font.size=Pt(16)
def table(head,rr):
 t=d.add_table(rows=1,cols=len(head));t.style='Light Shading'
 for c,s in zip(t.rows[0].cells,head):c.text=s
 for r in rr:
  for c,s in zip(t.add_row().cells,r):c.text=str(s)
names={'mean_deficit_core':'Core mean deficit','maintenance_core':'Core maintenance','peak_loss_core':'Core peak loss','mean_deficit':'Full mean deficit','log1p_dhrd':'log(1 + DHRD)'}
for i,kind in enumerate(('ntrd','dewpoint')):
 if i:d.add_page_break()
 d.add_heading('Supplementary Table S2 Limited heat interactions',0);d.add_heading('HD × '+('NTRD' if kind=='ntrd' else 'mean dewpoint'),1)
 rr=[r for r in rows if r['kind']==kind and r['estimable']];table(['Signal (events/countries)','Outcome','Slope [95% CR0]','BH / BY'],[[f"{r['signal']} ({r['n']}/{r['countries']})",names[r['outcome']],f"{r['beta']:.4g} [{r['interval95_normal_cr0'][0]:.4g}, {r['interval95_normal_cr0'][1]:.4g}]",f"{r['bh']:.4g} / {r['by']:.4g}"] for r in rr])
 d.add_paragraph('Each model separately extends the original A/M2 using the centered HD-by-modifier product, retaining all four main effects and country/start-year-month fixed effects on unchanged rows. HD/NTRD units are °C-days; dewpoint is °C. Slopes retain original ratio or log-outcome units, without percentage-point conversion. Centering means, all coefficients/covariances and raw p-values are retained in source.json.')
 d.add_paragraph('This requirement was completed after the primary results had been viewed. Normal country-CR0 intervals and a separate 30-case BH/BY family are approximate, not study-wide multiplicity or small-sample certification. The ten unavailable Telescope outcomes contribute 1 only to adjustment, never to raw p-values or coefficients. Every outcome is retained; in-sample residual variance reduction is not predictive performance.')
 d.add_paragraph('Telescope: 18 events / 17 countries; both M3 products and all five outcomes are unavailable because the original fixed effects leave no residual degrees of freedom. AP maintenance fitted values exceed the unit interval in 51/233 NTRD and 45/233 dewpoint rows; BGP in 198/384 and 186/384. These linear projections are not probabilities, and values were not clipped.')
d.add_page_break();d.add_heading('Supplementary Table S2 Full-window peak summary',0);table(['Signal','Events / countries','Median [IQR] full peak loss'],[[r['signal'],f"{r['n']}/{r['countries']}",f"{r['median']:.6g} [{r['q25']:.6g}, {r['q75']:.6g}]"] for r in peaks]);d.add_paragraph('This supplements Table 3 using unchanged original core-plus-72-hour peak deficits, not the core peaks in the main table. Denominators are complete observed windows without flagged interference, not the damaged-at-end conditional recovery sample. The peak is a normalized signal shortfall, not a fraction of residents disconnected. No threshold, exclusion, event boundary or source metric was recalculated.')
for tree in (d.styles.element,d.element):
 for b in tree.xpath('.//w:pBdr'):b.getparent().remove(b)
d.save(out/'interaction_tables.docx');(out/'manifest.json').write_text(json.dumps(dict(status='exported_render_pending',outputs={f.name:h(f) for f in out.iterdir()},whole_study_accepted=False),indent=2)+'\n');print(len(rows),peaks)
