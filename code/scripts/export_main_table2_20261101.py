"""Publish preserved dose-model objects and inference; no fitting or p-value selection."""
from pathlib import Path
import json,csv,hashlib
from docx import Document
from docx.shared import Inches,Pt,RGBColor
root=Path(__file__).resolve().parents[1];out=root/'deliverables/2026-11-01_main_table2';assert not out.exists()
files={'models':'analysis/2026-10-13_heat_associations/v2/full_outputs/results.json','inference':'analysis/2026-10-13_heat_inference/v1/full_outputs/inference.json','common':'analysis/2026-10-28_common_associations/v1/full_outputs/results.json'};data={}
for key,path in files.items():
 p=root/path;m=json.loads((p.parent/'manifest.json').read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==m['outputs'][p.name]['sha256'];data[key]=json.loads(p.read_text())
models={(r['signal'],r['setting'],r['model']):r for r in data['models']};inf={(r['signal'],r['setting'],r['model'],r['outcome'],r['term']):r for r in data['inference']};assert len(inf)==230
allrows=[]
for key,r in models.items():
 for outcome,f in r['results'].items():
  for idx,term in enumerate(r['terms']):
   z=inf[(*key,outcome,term)];assert z['estimable']==f['estimable']
   if f['estimable']:assert z['beta']==f['beta'][idx]
   allrows.append(dict(signal=key[0],setting=key[1],model=key[2],outcome=outcome,term=term,n=f['n'],countries=f['countries'],residual_df=f.get('residual_df'),estimable=f['estimable'],reason=f.get('reason'),beta=z.get('beta'),interval95_country_wild_basic=z.get('wcu_basic95'),interval95_normal_cr0=f.get('interval95_normal',[None]*len(r['terms']))[idx],p_normal_cr0=z.get('p_normal_cr0'),fdr_bh=z['fdr_bh'],fdr_by=z['fdr_by'],predicted_outside_unit_interval=f.get('predicted_outside_unit_interval')))
assert len(allrows)==230 and sum(r['estimable'] for r in allrows)==160
out.mkdir();(out/'all_230_slopes.json').write_text(json.dumps(allrows,indent=2,allow_nan=False)+'\n')
with (out/'all_230_slopes.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(allrows[0]));w.writeheader();w.writerows([{k:json.dumps(v) if isinstance(v,list) else v for k,v in row.items()} for row in allrows])
(out/'common_sample_unavailable.json').write_text(json.dumps(data['common'],indent=2)+'\n')
doc=Document();sec=doc.sections[0];sec.top_margin=sec.bottom_margin=Inches(.7);sec.left_margin=sec.right_margin=Inches(.65)
for st in ('Normal','Title','Heading 1','Heading 2'):doc.styles[st].font.name='Arial';doc.styles[st].font.color.rgb=RGBColor(0,0,0)
doc.styles['Normal'].font.size=Pt(9);doc.styles['Title'].font.size=Pt(16)
terms={'hd_c_days':'HD (°C-days)','span_days':'Event span (days)','peak_excess_c':'Peak excess (°C)','hot_days':'Hot days','bridge_days':'Bridge days','dewpoint_mean_c':'Mean dewpoint (°C)','ntrd_c_days':'NTRD (°C-days)'};outs=['mean_deficit_core','maintenance_core','peak_loss_core'];headers=['Term','Core mean deficit','Core maintenance','Core peak loss'];first=True
for signal,label in [('ping-slash24','AP'),('bgp','BGP')]:
 for setting in ('A','B'):
  if not first:doc.add_page_break()
  first=False;doc.add_heading('Table 2 Heat load and functional resistance',0);doc.add_heading(label+' '+('Cumulative heat load' if setting=='A' else 'Intensity and duration'),1)
  for model in ('M1','M2'):
   r=models[signal,setting,model];f=r['results'][outs[0]];doc.add_heading(f"{model}   {f['n']} events   {f['countries']} countries",2);table=doc.add_table(rows=1,cols=4);table.style='Light Shading'
   for cell,text in zip(table.rows[0].cells,headers):cell.text=text
   for term in r['terms']:
    vals=[terms[term]]
    for o in outs:
     z=inf[signal,setting,model,o,term];ci=z['wcu_basic95'];vals.append(f"{100*z['beta']:.3g} [{100*ci[0]:.3g}, {100*ci[1]:.3g}]")
    for cell,text in zip(table.add_row().cells,vals):cell.text=text
  doc.add_paragraph('Entries are percentage-point slope differences per original exposure unit, with 95% country wild basic intervals. Equal-event models include country and event-start year-month fixed effects. M2 adds NTRD to M1 on the same event sample. These conditional slopes are not heat-versus-nonheat effects or causal estimates.')
  doc.add_paragraph('Intervals are unadjusted and nonstudentized. The accompanying 230-slope table retains all five outcomes, original ratio/log scales, normal CR0 intervals/p-values and the retrospective BH/BY diagnostic. Those adjustments apply to normal p-values, not to wild intervals; unavailable comparisons retain missing estimates, never zero effects.')
doc.add_page_break();doc.add_heading('Unsupported and shared samples',1)
for signal,label in [('merit-nt','Telescope')]:
 for setting in ('A','B'):
  for model in ('M1','M2'):
   f=models[signal,setting,model]['results'][outs[0]];assert not f['estimable'];doc.add_paragraph(f"{label} {setting}/{model}: {f['n']} events, {f['countries']} countries; {f['reason']}. All outcome coefficients remain unavailable.")
assert len(data['common'])==12
for r in data['common']:
 for f in r['results'].values():assert not f['estimable']
f=data['common'][0]['results'][outs[0]];doc.add_paragraph(f"The cross-signal common integral cohort has {f['n']} events in {f['countries']} countries per signal. All 60 outcome specifications have no residual degrees of freedom under the original fixed effects. Shared-sample slopes are unavailable; no arbitrary pseudoinverse or zero coefficient is substituted. Structural term omissions are preserved in source model objects.")
doc.add_paragraph('Log(1+DHRD) slopes in the supplementary numerical table are not marginal DHRD-hour differences. Integration length mechanically affects accumulated deficit; the intensity-duration model retains bridge days separately. Prediction-boundary diagnostics are retained for ratio outcomes.')
for tree in (doc.styles.element,doc.element):
 for border in tree.xpath('.//w:pBdr'):border.getparent().remove(border)
doc.save(out/'table2.docx');(out/'manifest.json').write_text(json.dumps(dict(status='numerical_source_linkage_passed_render_pending',source_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files.values()},outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()},whole_study_accepted=False),indent=2)+'\n');print(len(allrows))
