"""Format existing duration/recovery data without new fits or changing denominators."""
from pathlib import Path
import json,hashlib,csv
from collections import Counter
import numpy as np
from docx import Document
from docx.shared import Inches,Pt,RGBColor
root=Path(__file__).resolve().parents[1];out=root/'deliverables/2026-11-01_main_table3_v2';assert not out.exists()
paths=['analysis/2026-10-12_resilience_metrics/v1/full_outputs/event_metrics.json','analysis/2026-10-15_recovery_qualification/v1/full_outputs/rows.json','deliverables/2026-11-01_primary_figures_v2/source_data.json','analysis/2026-10-13_event_panel/v1/full_outputs/manifest.json']
raw=[json.loads((root/p).read_text()) for p in paths];metrics,risk,fig,parent=raw
expected=parent['inputs'][paths[0]];assert hashlib.sha256((root/paths[0]).read_bytes()).hexdigest()==expected['sha256']
labels={'ping-slash24':'AP','bgp':'BGP','merit-nt':'Telescope'};signals=list(labels);states=['no_significant_deficit','delayed_onset','damaged_at_end','stable_recovered_before_end','awaiting_confirmation','insufficient_observation']
state_names=['No full-window threshold shortfall','Delayed onset','Damaged at event end','Stable recovery before event end','Awaiting confirmation','Insufficient full-window observation']
a=[];b=[];c=[]
for sig in signals:
 rows=[x for x in metrics if x['signal']==sig];counts=Counter(x['metrics']['state'] for x in rows);assert dict(counts)==fig['technical_states'][sig] and len(rows)==910
 for state,name in zip(states,state_names):a.append(dict(signal=labels[sig],state=state,label=name,n=counts[state],denominator=len(rows),percent=counts[state]/len(rows)*100))
 clean=[x for x in rows if x['full_observed_unconfounded'] and x['metrics']['full_window_complete']];assert len(clean)=={'ping-slash24':466,'bgp':601,'merit-nt':302}[sig]
 fields={'dhrd_hours':'DHRD (deficit-hours)','mean_deficit':'Mean full-window deficit (ratio)','disruption_hours_full':'Full-window time below 95% (hours)','disruption_hours_core':'Core time below 95% (hours)','disruption_hours_post':'Post-event time below 95% (hours)','maintenance_core':'Core maintenance (fraction)','peak_loss_core':'Core peak loss (ratio)'}
 for field,label in fields.items():
  vv=np.array([x['metrics'][field] for x in clean],float);assert np.isfinite(vv).all();qq=np.quantile(vv,[.25,.5,.75],method='linear')
  b.append(dict(signal=labels[sig],field=field,label=label,n=len(vv),countries=len({x['country_id'] for x in clean}),q25=float(qq[0]),median=float(qq[1]),q75=float(qq[2])))
 rr=[r for r in risk if r['signal']==sig and r['qualified']['risk_eligible']];pos=[r for r in rr if r['qualified']['recovery']['followup_hours']>0]
 statuses=Counter(r['qualified']['recovery']['status'] for r in pos);causes=Counter(r['qualified']['censor_cause'] for r in pos if r['qualified']['censor_cause'])
 golden=next(x for x in fig['conditional_recovery'] if x['signal']==sig and x['sample']=='primary' and x['model']=='M1');assert len(pos)==golden['rows'] and statuses['confirmed']==golden['events']
 c.append(dict(signal=labels[sig],qualified_core_risk=len(rr),zero_followup=len(rr)-len(pos),positive_followup=len(pos),countries=len({x['country_id'] for x in pos}),confirmed=statuses['confirmed'],right_censored_72h=statuses['right_censored_72h'],missingness_censored=statuses['missingness_censored'],administrative_censored=statuses['administrative_censored'],causes=dict(causes)))
notes=['Panel A uses all 910 forward technical records per signal, including observation insufficiency; these are not all global heat events or confirmed heat failures.', 'Panel B uses complete observed integral windows without flagged interference (AP 466/129 countries; BGP 601/137; Telescope 302/93). Medians [25th, 75th percentiles] describe selected events; no heat-versus-control contrast is implied. A ratio shortfall is not a fraction of people disconnected.', 'Panel C conditions on observed damaged-at-end cores. Unlike Panel A classification, it does not require complete subsequent observation; it can therefore contain more damaged cores than Panel A. First missing/flagged follow-up censors. Telescope has one eligible zero-follow-up record excluded from positive-time fits. Administrative and missingness censoring are not known 72-hour non-recovery.', 'AP recovery is sparse and exploratory; BGP has no confirmed endpoints and no fitted recovery effect. Confirmation requires 24 consecutive ten-minute slots at or above 95%. These panels are distinct denominators and must not be added together.']
out.mkdir();obj=dict(states=a,distributions=b,conditional_recovery=c,notes=notes,source_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},whole_study_accepted=False)
(out/'table3_source.json').write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
for name,rows in [('states',a),('distributions',b),('conditional_recovery',c)]:
 with (out/(name+'.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows([{k:json.dumps(v) if isinstance(v,dict) else v for k,v in r.items()} for r in rows])
doc=Document();sec=doc.sections[0];sec.top_margin=sec.bottom_margin=Inches(.7);sec.left_margin=sec.right_margin=Inches(.7)
for style in ('Normal','Title','Heading 1','Heading 2'):
 doc.styles[style].font.name='Arial';doc.styles[style].font.color.rgb=RGBColor(0,0,0)
doc.styles['Title'].font.size=Pt(16)
doc.styles['Normal'].font.size=Pt(9);doc.styles['Normal'].paragraph_format.space_after=Pt(5)
def table(headers,rows):
 t=doc.add_table(rows=1,cols=len(headers));t.style='Light Shading'
 for cell,text in zip(t.rows[0].cells,headers):cell.text=text
 for row in rows:
  for cell,text in zip(t.add_row().cells,row):cell.text=str(text)
 return t
names=list(labels.values());doc.add_heading('Table 3 Duration observed states and conditional recovery',0);doc.add_heading('A All forward technical records',1)
table(['State',*names],[[name,*[f"{r['n']} ({r['percent']:.1f}%)" for sig in names for r in a if r['signal']==sig and r['state']==state]] for state,name in zip(states,state_names)])
doc.add_paragraph(notes[0]);doc.add_heading('B Complete observed windows without flagged interference',1)
table(['Metric',*names],[[label,*[f"{r['median']:.4g} [{r['q25']:.4g}, {r['q75']:.4g}]" for sig in names for r in b if r['signal']==sig and r['field']==field]] for field,label in fields.items()]);doc.add_paragraph(notes[1]);doc.add_page_break();doc.add_heading('C Core conditioned recovery and censoring',1)
for key,label in [('qualified_core_risk','Qualified core risk'),('zero_followup','Zero observable follow-up'),('positive_followup','Positive-time risk sample'),('countries','Countries in positive-time sample'),('confirmed','Confirmed recovery'),('right_censored_72h','Right-censored at 72 hours'),('missingness_censored','Missingness/flag censoring'),('administrative_censored','Administrative censoring')]:
 if key=='qualified_core_risk':rows=[]
 rows.append([label,*[r[key] for r in c]])
table(['Category',*names],rows)
for n in notes[2:]:doc.add_paragraph(n)
for r in c:doc.add_paragraph(r['signal']+' first-censor causes among positive-time records: '+(', '.join(k.replace('_',' ')+': '+str(v) for k,v in r['causes'].items()) or 'none')+'.')
for tree in (doc.styles.element,doc.element):
 for border in tree.xpath('.//w:pBdr'):border.getparent().remove(border)
doc.save(out/'table3.docx');receipt=dict(status='numerical_cross_source_checks_passed_render_pending',outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()},scope='One formatted main table component; not the complete four-table set, manuscript integration or whole-study acceptance.')
(out/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(c))
