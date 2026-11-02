"""Preserved modifier/support and separate DLEP tables, no refits or selected outcomes."""
from pathlib import Path
import json,csv,hashlib
from collections import Counter
from docx import Document
from docx.shared import Inches,Pt,RGBColor
root=Path(__file__).resolve().parents[1];out=root/'deliverables/2026-11-01_main_table4';assert not out.exists()
files=['analysis/2026-10-19_modifier_models/v2/full_outputs/results.json','analysis/2026-10-19_temporal_modifiers/v1/full_outputs/rows.json','analysis/2026-10-20_dlep/v1/full_outputs/summary.json'];payload=[]
for name in files:
 p=root/name;m=json.loads((p.parent/'manifest.json').read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==m['outputs'][p.name]['sha256'];payload.append(json.loads(p.read_text()))
models,inputs,dlep=payload;assert len(models)==18
labels={'ping-slash24':'AP','bgp':'BGP','merit-nt':'Telescope'};names={'pre_connection_dispersion':'Pre-event MAD / median','electricity_access_share':'Electricity access','gdp_per_capita_ppp_constant':'GDP per capita PPP','urban_population_share':'Urban population','internet_share':'Internet use','first_warm_season_event':'First seasonal event'};support=[];effects=[];years=[]
for r in models:
 support.append(dict(signal=labels[r['signal']],modifier=r['modifier'],available=r['available'],supported=r['supported'],groups=r.get('post_support'),reason=r.get('reason'),bh_range=[min(x['bh'] for x in r['adjustment'].values()),max(x['bh'] for x in r['adjustment'].values())] if r['supported'] else None))
 for outcome in ('mean_deficit_core','maintenance_core','peak_loss_core'):
  f=r['results'].get(outcome,{});ok=f.get('estimable',False);i=r['terms'].index('hd_x_modifier') if ok else None
  effects.append(dict(signal=labels[r['signal']],modifier=r['modifier'],outcome=outcome,supported=r['supported'],estimable=ok,n=f.get('n'),countries=f.get('countries'),beta=f['beta'][i] if ok else None,interval95_normal_cr0=f['interval95_normal'][i] if ok else None,p_normal_cr0=f.get('interaction_p_normal'),bh=r['adjustment'][outcome]['bh'],by=r['adjustment'][outcome]['by'],modifier_center=r.get('modifier_center'),modifier_scale=r.get('modifier_scale'),reason=r.get('reason',f.get('reason'))))
for signal in labels:
 rows=[r for r in inputs if r['signal']==signal and r['matched_integral']]
 for name in ('electricity_access_share','gdp_per_capita_ppp_constant','urban_population_share','internet_share'):
  vals=[r['modifiers'][name] for r in rows if r['modifiers'][name]['value'] is not None];sy=sorted(set(v['source_year'] for v in vals));lags=Counter(v['lag_years'] for v in vals);assert all(1<=k<=3 for k in lags)
  years.append(dict(signal=labels[signal],modifier=name,matched_records=len(rows),available=len(vals),missing=len(rows)-len(vals),source_years=sy,lags=dict(lags)))
assert len(effects)==54 and sum(e['estimable'] for e in effects)==30 and not any(e['bh']<=.05 or e['by']<=.05 for e in effects if e['estimable'])
out.mkdir();obj=dict(support=support,all_54_interactions=effects,indicator_years=years,dlep=dlep,original_modifier_objects=models,scope='Six prespecified modifiers; 54-case BH/BY, marginal support only. DLEP separate retrospective weighting. No ranking, policy effect or full-study acceptance.',source_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files});(out/'table4_source.json').write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
for name,rows in [('support',support),('all_54_interactions',effects),('indicator_years',years)]:
 with (out/(name+'.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows([{k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in rows])
doc=Document();sec=doc.sections[0];sec.top_margin=sec.bottom_margin=Inches(.7);sec.left_margin=sec.right_margin=Inches(.65)
for st in ('Normal','Title','Heading 1','Heading 2'):doc.styles[st].font.name='Arial';doc.styles[st].font.color.rgb=RGBColor(0,0,0)
doc.styles['Normal'].font.size=Pt(9);doc.styles['Title'].font.size=Pt(16)
def table(headers,rows):
 t=doc.add_table(rows=1,cols=len(headers));t.style='Light Shading'
 for c,s in zip(t.rows[0].cells,headers):c.text=s
 for row in rows:
  for c,s in zip(t.add_row().cells,row):c.text=str(s)
for idx,label in enumerate(labels.values()):
 if idx:doc.add_page_break()
 doc.add_heading('Table 4 Conditional modifiers and social weighting',0);doc.add_heading(label+' modifier support',1);rr=[r for r in support if r['signal']==label]
 rows=[]
 for r in rr:
  groups=r['groups'];low=f"{groups[0]['events']}/{groups[0]['countries']}" if groups else 'Not split';high=f"{groups[1]['events']}/{groups[1]['countries']}" if groups else 'Not split';bh=r['bh_range'];fdr=f"{bh[0]:.3g}–{bh[1]:.3g}" if bh else 'Unavailable';rows.append([names[r['modifier']],r['available'],low,high,fdr])
 table(['Modifier','Available','Low n/c','High n/c','BH range'],rows)
 doc.add_paragraph('n/c denotes events/countries after the original marginal-range support restriction. Continuous groups split at the available-sample median; the first-event indicator splits false/true. At least 10 events and 5 countries per arm are required. The pre-connection MAD descriptor is excluded from the support axes when it defines the groups. Marginal overlap is not proof of joint overlap.')
 doc.add_paragraph('The BH range covers all three prespecified interaction outcomes (core mean deficit, maintenance and peak loss); it is a reporting range, not a new combined test. No estimated interaction passed BH or BY at 0.05; this does not establish no modification. All 54 numerical cases, coefficients, normal CR0 intervals, original p-values, BH/BY and unsupported reasons are retained in the accompanying table. Unavailable adjustments use placeholders only inside the original family, never as observed p-values.')
 for r in rr:
  if not r['supported']:doc.add_paragraph(names[r['modifier']]+': '+r['reason']+'.')
 doc.add_paragraph('Model interaction coefficients use one original HD unit times one available-sample standard deviation of a continuous modifier; the first-event contrast uses a unit false-to-true change. These are exploratory conditional associations, not intervention or learning effects. Source units and scaling are retained in the numerical appendix.')
doc.add_page_break();doc.add_heading('Indicator timing and missing values',1)
for label in labels.values():
 doc.add_heading(label,2);rows=[]
 for r in years:
  if r['signal']==label:rows.append([names[r['modifier']],f"{r['available']}/{r['matched_records']}",r['missing'],','.join(map(str,r['source_years'])),', '.join(str(k)+':'+str(v) for k,v in sorted(r['lags'].items()))])
 table(['Indicator','Observed / matched','Missing','Source years','Lag years counts'],rows)
doc.add_paragraph('Capability modifiers use the newest valid earlier calendar-year observation within three years; publication timestamps are unavailable, so actual release-time availability is not certified. Shares are fractions; GDP retains the archived constant-PPP source units. No missing value is interpolated or set to zero. Counts here precede modifier-specific support trimming. Pre-event dispersion is dimensionless; first seasonal event is a weather-catalogue indicator.')
doc.add_page_break();doc.add_heading('DLEP as a separate descriptive proxy',1);rows=[]
for key,label in [('full_clean_ap','Full observed AP'),('matched_integral_ap','Matched integral AP')]:
 g=dlep['groups'][key];q=g['proxy_quantiles'];rows.append([label,f"{g['available']}/{g['records']}",g['countries'],f"{q['0.5']:.4g} [{q['0.25']:.4g}, {q['0.75']:.4g}]",', '.join(str(k)+':'+str(v) for k,v in sorted(g['source_lags'].items()))])
table(['AP cohort','Available / records','Countries','Proxy median [IQR]','Internet-year lag counts'],rows)
doc.add_paragraph('DLEP multiplies AP DHRD by fixed 2025 assigned population and an Internet-use fraction. Its retrospective weighting prefers the event calendar year, then the latest valid earlier year within three years; this differs from the strictly lagged capability modifiers above. Twelve of 466 full observed AP records and eight of 233 matched integral AP records lack allowed Internet values. Valid zero proxies remain zero.')
doc.add_paragraph('The proxy is not observed disconnected people or person-hours, a welfare estimate, a resilience score or a country ranking. Source release dates and historical population changes are not established. Technical responses and social weighting remain separate.')
for tree in (doc.styles.element,doc.element):
 for border in tree.xpath('.//w:pBdr'):border.getparent().remove(border)
doc.save(out/'table4.docx');(out/'manifest.json').write_text(json.dumps(dict(status='source_hashes_and_family_counts_verified_render_pending',source_sha256=obj['source_sha256'],outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()},whole_study_accepted=False),indent=2)+'\n');print(len(effects),len(years))
