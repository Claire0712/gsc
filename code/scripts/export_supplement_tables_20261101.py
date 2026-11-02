"""Package existing definitions, all signed day-zero sensitivities and exclusion flags."""
import json,csv,hashlib
from pathlib import Path
from collections import Counter
from docx import Document
from docx.shared import Inches,Pt,RGBColor
root=Path(__file__).resolve().parents[1];out=root/'deliverables/2026-11-01_supplement_tables_v3';assert not out.exists();h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
variables=[
('Tmax','°C','ERA5 t2m and fixed population','UTC daily pixel maximum before country aggregation; not maximum of country hourly averages.'),
('Tmin','°C','ERA5 t2m and fixed population','UTC daily pixel minimum; not exact civil-night temperature and never changes the Tmax event end.'),
('Dewpoint','°C','ERA5 d2m','Hourly-derived daily country mean; not an observed equipment heat index.'),
('Q90','°C','2018–2021 Tmax/Tmin','Circular 365-day ±15-day window, linear quantile; at least 112 observations/all four years. Feb 29 averages adjacent thresholds.'),
('Warm season','start month','2018–2021 Tmax','Hottest consecutive three months by day-weighted mean; earliest start breaks ties; LOYO stability reported.'),
('Heat load HD','°C-days','Tmax excess over Q90','Sum of positive Tmax excess within the fixed analysis event; bridge days retain zero excess.'),
('Hot days and span','days','Tmax-only catalogue','Hot days count exceedances; span includes bridges. Analysis processes merge until seven complete cool days separate them.'),
('NTRD','°C-days','Tmin excess over its Q90','Positive Tmin excess over the same fixed Tmax event; secondary load only.'),
('Connection reference','signal units','IODA ten-minute grid','Median of eligible same-weekday/time observations ±7/14/21/28 days; at least 4 eligible references with both temporal sides; valid zeros count, but the final median must be positive. Retrospective.'),
('Signed deviation','ratio','C / reference − 1','Keeps positive and negative fluctuations; not percentage of residents disconnected.'),
('Truncated deficit','ratio','max(0,1 − C/reference)','Nonnegative shortfall; ordinary fluctuations can produce positive deficits.'),
('Core maintenance','fraction','IODA/reference','Core slots with ratio at least 0.95 divided by all required core slots; not an SLA.'),
('Core and full peak loss','ratio','IODA/reference','Maximum truncated deficit within core or core plus 72 hours, separately labelled.'),
('DHRD','deficit-hours','IODA/reference','Deficit sum times 1/6 hour over the entire fixed core plus 72 hours; incomplete windows remain missing.'),
('Unit-time deficit','ratio','DHRD / required hours','Mean full-window truncated deficit; separates accumulation length from average deficit.'),
('Disruption duration','hours','IODA/reference','Slots below 0.95 times 1/6 hour, separately for core, post-event and full window.'),
('Stable recovery','hours after Tmax end','Core-conditioned IODA/reference','Completion of 24 consecutive ten-minute slots at or above 0.95; 72-hour, administrative and missingness censoring distinct.'),
('Pre-event stability','MAD / median','Raw pre-event IODA','Dimensionless connection dispersion, not physical backup power or adaptation capacity.'),
('Capability modifiers','source units / fractions','World Bank','Newest valid prior year within 3 years; publication-time availability unknown. GDP retains constant-PPP archive units.'),
('DLEP','population-weighted deficit proxy','AP DHRD × fixed 2025 population × Internet fraction','Current calendar year preferred then recent prior 3 years; separate from strictly lagged capability modifiers; not actual disconnected people/person-hours.'),
('Precipitation adjustment','mm per UTC day','ERA5-Land accumulated precipitation','Audited daily labels and fixed-population support; only a supported daily subset, not certified adjustment in all primary models.'),
('Wind','m s⁻¹','Existing 2024 u/v country means','Magnitude of mean components, not gust or mean scalar speed; four retained months and paired subset only.')]
curvefiles=[('Heat definitions','deliverables/2026-10-16/ALL_VARIANT_CURVE_TABLES_2026-10-23.json'),('Cyclone masks','deliverables/2026-10-25_CYCLONE_ALL_CURVES.json'),('Hypothetical STOP dates','deliverables/2026-10-16/STOP_FULL_REFERENCE_CURVES_2026-10-24.json'),('Synchronous candidates','deliverables/2026-10-27_SYNC_CURVES.json'),('Reference-year omissions','deliverables/2026-10-28_LOYO_CURVES.json'),('Daily precipitation subset','deliverables/2026-10-29_PRECIPITATION_DAILY_CURVES.json'),('Calendar-block translations','deliverables/2026-10-30_CALENDAR_BLOCK_CURVES.json'),('Nonheat pseudo-events','deliverables/2026-10-30_NONHEAT_PLACEBO_CURVES.json')]
more=['deliverables/2026-10-28_ALTERNATIVE_BASELINE_MODELS.json','deliverables/2026-10-28_LOYO_MODELS.json','deliverables/2026-10-26_RECOVERY_DEFINITION_MODELS.json','deliverables/2026-10-28_COMMON_SAMPLE_MODELS.json','deliverables/2026-10-25_REGION_DELETION_ALL_SPECIFICATIONS.json','deliverables/2026-10-24/COUNTRY_DELETION_ALL_SPECIFICATIONS_2026-10-24.json','deliverables/2026-11-01_COUNTRY_SOLAR_DEFINITION_COMPARISON.json','deliverables/2026-11-01_PIXEL_SPATIAL_COMPARISON.json','deliverables/2026-11-01_SEVEN_YEAR_WEATHER_COMPARISON.json','deliverables/2026-10-31_ADM1_NATIVE_SUPPORT.json','deliverables/2026-11-01_GEOGRAPHIC_COMPARISON.json','analysis/2026-10-29_temperature_product_agreement/v1/summary.json','analysis/2026-10-19_wind_curve/v1/full_outputs/summary.json','deliverables/2026-11-01_main_table2/all_230_slopes.json','deliverables/2026-11-01_main_table4/all_54_interactions.csv']
rows=[];unavailable=[];overview=[];sources={}
for family,file in curvefiles:
 d=json.loads((root/file).read_text());sources[file]=h(root/file);cc=d['coefficients'];diag=d.get('diagnostics',[])
 for r in cc:
  if r['outcome']=='signed' and r['term']=='heat_day_0':
   identity={k:v for k,v in r.items() if k not in ('outcome','term','beta','country_wild_basic95','groups','countries','draws','enumerated','signal')};rows.append(dict(family=family,source=file,signal=r['signal'],specification=identity,groups=r['groups'],countries=r['countries'],beta=r['beta'],interval95_country_wild_basic=r['country_wild_basic95']))
 for r in d.get('unavailable',[]):unavailable.append(dict(family=family,source=file,record=r))
 overview.append(dict(family=family,source=file,coefficient_rows=len(cc),diagnostic_rows=len(diag),non_psd_diagnostics=sum(r.get('psd') is False for r in diag),unavailable_records=len(d.get('unavailable',[])),scope=d['scope']))
for file in more:sources[file]=h(root/file)
metricsfile='analysis/2026-10-12_resilience_metrics/v1/full_outputs/event_metrics.json';eventsfile='outputs/2026-11-01_seven_year_metadata/analysis_events.csv';m=json.loads((root/metricsfile).read_text());sources[metricsfile]=h(root/metricsfile)
reasons=Counter(k for r in m for k in r['qualification_reasons']);exclusions=[dict(level='technical signal-event records',reason=k,count=v,denominator=len(m),mutually_exclusive=False) for k,v in sorted(reasons.items())]
import pandas as pd
e=pd.read_csv(root/eventsfile);sources[eventsfile]=h(root/eventsfile)
for k in ('in_warm_season','complete_analysis_window','complete_weather_window','isolated_weather_event'):exclusions.append(dict(level='all intersecting weather events',reason='fails_'+k,count=int((~e[k]).sum()),denominator=len(e),mutually_exclusive=False))
for k,v in [('boundary_not_found',21),('source_not_exact',37)]:exclusions.append(dict(level='joint source entity mapping',reason=k,count=v,denominator=253,mutually_exclusive=True))
out.mkdir();obj=dict(variables=[dict(variable=v,unit=u,source=s,definition=d) for v,u,s,d in variables],signed_day_zero=rows,unavailable=unavailable,curve_family_overview=overview,exclusion_counts=exclusions,source_sha256=sources,scope='All declared existing evidence retained. Day zero signed presentation is a fixed primary outcome/time slice; all original outcomes/specifications remain in source artefacts. No new fit, cross-family multiplicity/equivalence or causal certification.',whole_study_accepted=False);(out/'supplement_source.json').write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
for name,rr in [('S1_variables',obj['variables']),('S2_signed_day_zero',rows),('S2_curve_family_overview',overview),('S2_unavailable',unavailable),('S3_exclusion_counts',exclusions)]:
 with (out/(name+'.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows([{k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rr])
(out/'source_index.json').write_text(json.dumps({f:dict(sha256=s,bytes=(root/f).stat().st_size) for f,s in sources.items()},indent=2)+'\n')
doc=Document();sec=doc.sections[0];sec.top_margin=sec.bottom_margin=Inches(.7);sec.left_margin=sec.right_margin=Inches(.65)
for st in ('Normal','Title','Heading 1','Heading 2'):doc.styles[st].font.name='Arial';doc.styles[st].font.color.rgb=RGBColor(0,0,0)
doc.styles['Normal'].font.size=Pt(9);doc.styles['Title'].font.size=Pt(16)
def table(headers,rr):
 t=doc.add_table(rows=1,cols=len(headers));t.style='Light Shading'
 for c,s in zip(t.rows[0].cells,headers):c.text=s
 for row in rr:
  for c,s in zip(t.add_row().cells,row):c.text=str(s)
def page(title):
 if doc.paragraphs:doc.add_page_break()
 doc.add_heading(title,0)
for start in range(0,len(variables),8):
 page('Supplementary Table S1 Variables and retained sources');table(['Variable and unit','Source','Definition and boundary'],[[v+' ('+u+')',s,d] for v,u,s,d in variables[start:start+8]])
signal_names={'ping-slash24':'AP','bgp':'BGP','merit-nt':'Telescope'}
def display_spec(d):
 if 'variant' in d:return {'absolute35':'Absolute Tmax >35°C','absolute30':'Absolute Tmax >30°C','q95':'Q95 threshold','min3':'Minimum run 3 days','min6':'Minimum run 6 days','season6':'Six-month season','all_year':'All-year inclusion'}[d['variant']]
 if 'scenario' in d:
  value=d['scenario']
  if value.startswith('unknown_end_plusminus'):return 'Hypothetical end ±'+value.rsplit('plusminus',1)[1]+' days'
  radius,hours=value.split('_');return radius+' km, ±'+hours+' hours'
 if 'omitted_reference_year' in d:return 'Omit reference '+str(d['omitted_reference_year'])
 if 'universe' in d:return 'Exact-joint universe' if d['universe']=='joint' else 'All-source universe'
 if 'model' in d:return 'Same-sample base' if d['model']=='base' else 'Same-sample precipitation'
 if 'shift_days' in d:return str(d['shift_days'])+' day translation'
 return 'Nonheat pseudo-events'
for family,file in curvefiles:
 selected=[r for r in rows if r['family']==family]
 for start in range(0,len(selected),12):
  page('Supplementary Table S2 Sensitivity estimates');doc.add_heading(family,1);rr=[]
  for r in selected[start:start+12]:
   ident=display_spec(r['specification']);ci=r['interval95_country_wild_basic'];rr.append([ident,signal_names[r['signal']],f"{r['groups']}/{r['countries']}",f"{100*r['beta']:.3g} [{100*ci[0]:.3g}, {100*ci[1]:.3g}]"])
  table(['Specification','Signal','Events / countries','Signed day zero pp [95%]'],rr);doc.add_paragraph('Unadjusted country-wild basic intervals, not studentized or cross-family multiplicity adjusted. Different definitions can change samples; entries are not paired equivalence tests. All source coefficients, other outcomes and diagnostics remain available. Positive and negative slices are retained. Very small country counts limit interval calibration.')
  if family=='Hypothetical STOP dates':doc.add_paragraph('Unknown-end ±7/30 day masks are hypothetical sensitivity windows, never reconstructed shutdown end dates.')
  if family=='Synchronous candidates':doc.add_paragraph('Joint/all candidate universes are separate; unconfirmed coincident drops are not established platform faults.')
  if family=='Calendar-block translations':doc.add_paragraph('Whole 15-day blocks shift ±28/56 days using observed source-date support. Sparse support and small clusters remain; this is not a calibrated random-permutation null.')
page('Supplementary Table S2 Additional numerical evidence')
table(['Evidence family','Content and interpretation'],[
 ['Alternative baselines and exclusions','Ten preselected sensitivity protocols; all emitted dose/recovery models and absent-signal reasons retained. Samples change, so comparisons are not paired causal contrasts.'],
 ['Reference-year omissions','All four original reference years omitted separately, with dose and recovery models rebuilt. Short-reference sensitivity is distinct from long-climate uncertainty or a same-sample effect test.'],
 ['Recovery definitions','Four one-factor threshold/confirmation alternatives, both primary and complete72 risk sets and M1/M2. Conditional endpoints differ; numerical health criteria were post-hoc and applied uniformly.'],
 ['Cross-signal common sample','254 common full-observed events for conditional recovery; 14 common integral-matched events for dose. No fixed effects removed to manufacture a dose estimate; future completeness conditions the selected samples.'],
 ['Region deletion','All signals, heat settings and nested models. Archived region categories are not historical event-year classifications. Ranges over refits are not confidence intervals or independent replications.'],
 ['Country deletion','All supported country omissions retained, including structural term omissions and unestimability. Empty ranges remain missing, never zero effects; numerical agreement does not establish identification.']])
doc.add_paragraph('The source index binds exact files and hashes. Country/region deletion ranges are ranges over refits, not confidence intervals. Recovery alternatives change the conditional endpoint/risk set; complete72 conditions on future completeness. Alternative baseline samples are not paired causal contrasts.')
page('Supplementary Table S2 Measurement and support diagnostics')
solar=json.loads((root/more[6]).read_text());pix=json.loads((root/more[7]).read_text());seven=json.loads((root/more[8]).read_text());adm=json.loads((root/more[9]).read_text());old=json.loads((root/more[11]).read_text());wind=json.loads((root/more[12]).read_text())
table(['Diagnostic','Observed support or change','Boundary'],[['Country mean-solar clock',f"{solar['solar_events']} versus {solar['utc_events']} UTC events; {solar['same_full_bounds']} same bounds",'Fixed-population circular-mean country longitude; not civil night or a solar-day network effect.'],['Local pixel Q90',f"{pix['summary']['supported_country_days']} supported country-days, {pix['summary']['countries']} identifiers",'Population fractions are spatial weather diagnostics, not fault footprints.'],['Seven-other-year reference',f"{seven['summary']['events']} / {seven['summary']['weather_candidates']} events / candidates",'Target-year cohorts; later observations enter 2022–24 references. No alternative connectivity effect certified.'],['ADM1 native support',f"{adm['summary']['unique_regions']} regions; {adm['summary']['native_coverage80']}/{adm['summary']['region_source_years']} region/source/years at 80%",'Native support is not ten-minute or approved geometric linkage; no ADM1 network-effect claim.'],['Old temperature product',f"{old['summary']['tmax_c']['country_days']} paired country-days, {old['summary']['tmax_c']['countries']} identifiers",'Retained 2024 Jan/Feb/Mar/July only; old minus main Tmax mean '+format(old['summary']['tmax_c']['mean_difference_c'],'.4g')+'°C. Measurement agreement, not independent truth or product-specific event-effect replication.'],['Wind paired subset','AP 3 and BGP 4 event groups; Telescope unsupported','Magnitude of daily mean u/v; sparse four-month support and native reassignment certification limits.']])
page('Supplementary Table S3 Exclusion and unresolved-review audit')
table(['Level','Reason','Count / denominator'],[[r['level'],r['reason'].replace('_',' '),f"{r['count']}/{r['denominator']}"] for r in exclusions]);doc.add_paragraph('Reasons overlap within technical or weather records and must not be added as a sequential funnel. The two mapping statuses are exclusive categories within 253 source entities. Four zero-population boundary units remain excluded from climate aggregation and are not imputed.')
doc.add_paragraph('The original stage flag final_sample_review_not_completed remains on all 2730 technical records and is not silently rewritten as true. It records the archived workflow status; reporting uses the explicitly defined technical observation/mask criteria. Unresolved STOP-end records remain uncertain and receive hypothetical sensitivity masks. Neither this metadata nor a synchronous candidate establishes a confirmed fault or heat cause.')
doc.add_paragraph('Complete observed windows and core-conditioned recovery have different denominators (Table 3). Missing observation/reference, flagged interference, weak matching and absent residual degrees of freedom produce missing estimates, not safe or zero-effect labels. The source index preserves all unsupported-model reasons and unchanged numerical objects.')
for tree in (doc.styles.element,doc.element):
 for b in tree.xpath('.//w:pBdr'):b.getparent().remove(b)
doc.save(out/'supplement_tables.docx');(out/'manifest.json').write_text(json.dumps(dict(status='source_index_and_counts_written_render_pending',outputs={p.name:h(p) for p in out.iterdir()},whole_study_accepted=False),indent=2)+'\n');print(len(rows),len(unavailable),len(exclusions))
