"""Consolidate supported manuscript components without changing model results."""
from pathlib import Path
import hashlib,json

root=Path(__file__).resolve().parents[1];base=root/'deliverables'
names=['2026-10-26_HeatSignal_essay_referenced_v10.txt',
       '2026-10-27_HeatSignal_sync_results_addendum.txt',
       '2026-10-28_HeatSignal_loyo_results_addendum.txt',
       '2026-10-28_HeatSignal_common_sample_addendum.txt']
texts=[(base/n).read_text() for n in names]
main=texts[0]
start=main.index('\nReferences\n');end=main.index('\nComplete lead diagnostics constrain interpretation',start)
references=main[start:end];main=main[:start]+main[end:]
old='The common-control curve refit addresses daily trajectory support, not\ncommon-sample event-level heat-dose or recovery models.'
assert main.count(old)==1
main=main.replace(old,'The common-control curve refit addresses daily trajectory support. The completed common-sample event-level checks are reported below; they do not remove its support and selection limitations.')
old='as do separate DLEP social weighting and final reconciliation of threshold\nand season sensitivities.'
assert main.count(old)==1
main=main.replace(old,'DLEP weighting and the four omitted-reference-year curve and model tables have since been completed, as documented in the components and accompanying full tables.')
sync=texts[1]
old='remaining LOYO, placebo, precipitation or final delivery acceptance work.'
assert sync.count(old)==1
sync=sync.replace(old,'remaining placebo, precipitation or final delivery acceptance work. The separate LOYO curve and model components are now available below.')
loyo=texts[2]
old='This completes the curve-table component,\nnot LOYO dose/recovery-model sensitivity, the remaining mandatory analyses,\npublication figure acceptance, replay acceptance or final reproducibility QA.'
assert loyo.count(old)==1
loyo=loyo.replace(old,'This completes the curve-table component. LOYO dose and recovery results are summarized below and retained in the full model table. Remaining mandatory analyses, final publication, replay and reproducibility acceptance are not certified.')
tables={n:json.loads((base/n).read_text()) for n in ['2026-10-28_LOYO_MODELS.json','2026-10-28_ALTERNATIVE_BASELINE_MODELS.json']}
paragraphs=['Model support across short reference and exclusion alternatives\n']
for name,data in tables.items():
    family=data['families'];dose=family['associations']
    cox=next(v for k,v in family.items() if k!='associations')
    estimable=sum(all(r['estimable'] for r in row['results'].values()) for row in dose)
    good=sum(row['estimable'] for row in cox)
    if 'LOYO' in name:
        assert (len(dose),estimable,len(cox),good)==(48,32,48,32)
        paragraphs.append('All four omitted-reference-year dose and recovery chains were completed with the original model specifications and independent numerical audits. Of 48 emitted dose specifications, 32 were estimable; of 48 emitted conditional Cox specifications, 32 were estimable. All outcomes, coefficients, covariance diagnostics and unavailable reasons remain in '+name+'. These are emitted-specification counts, not counts of independent discoveries or distinct people. Each dose specification retains five outcomes.')
    else:
        assert (len(dose),estimable,len(cox),good)==(112,74,120,78)
        paragraphs.append('The ten previously specified alternative baseline or exclusion scenarios comprise five cyclone buffers, two hypothetical unknown-shutdown windows, two synchronous-candidate universes and the past-only reference. Their completed model export contains 112 emitted dose specifications, of which 74 were estimable, and 120 conditional Cox specifications, of which 78 were estimable. The two synchronous scenarios had no main-caliper Telescope integral support, so four dose specifications per scenario were not emitted and are explicitly listed separately rather than assigned zero effects. The full results and unavailable reasons are retained in '+name+'.')
paragraphs.append('Dose models preserve country and event-start year-month fixed effects and country-CR0 covariance. Conditional recovery models retain the existing uniformly applied post-hoc numerical-health rules; complete72 conditions on future completeness. Samples and eligibility can change across scenarios. Numerical acceptance does not establish paired same-event effects, calibrated small-cluster inference, multiplicity control, proportional hazards, independent censoring or causality. No definition was selected to obtain statistical significance.')
header='Digital connectivity resilience under heat stress\n\nConsolidated manuscript text as of 28 October 2026\n\nStudy acceptance remains incomplete. The 22:00 delivery deadline was not met; no replacement deadline or reduced scope is declared. This text integrates already available evidence and is not a submission-ready final manuscript. The outstanding analyses and acceptance checks remain in 2026-10-28_DELIVERY_STATUS.txt.\n\n'
output=base/'2026-10-28_HeatSignal_manuscript_text_v12.txt'
assert not output.exists()
content=header+'\n'.join(main.splitlines()[5:])+'\n\n'+sync+'\n\n'+loyo+'\n\n'+texts[3]+'\n\n'+'\n\n'.join(paragraphs)+references+'\n'
assert content.count('\nReferences\n')==1
assert content.index('\nReferences\n')>content.index('Model support across short reference')
output.write_text(content)
sources=names+list(tables)
receipt=dict(output=output.name,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
 sources={n:hashlib.sha256((base/n).read_bytes()).hexdigest() for n in sources},
 model_counts_checked=True,references_moved_after_results=True,whole_study_accepted=False,
 docx_v11_superseded_for_text_only=True)
path=root/'outputs/2026-10-28_manuscript_text_v12_receipt.json'
assert not path.exists();path.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
