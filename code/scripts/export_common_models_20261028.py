"""Complete common-membership model tables; do not fabricate absent BGP risk."""
import json
from .summarize_stop_target_curves_20261023 import ROOT,verified

dose=verified('analysis/2026-10-28_common_associations/v1/full_outputs','results.json')
cox=verified('analysis/2026-10-28_common_cox/v2/full_outputs','results.json')
risk=verified('analysis/2026-10-28_common_qualification/v1/full_outputs','summary.json')
assert len(dose)==12 and not any(o['estimable'] for r in dose for o in r['results'].values())
assert len(cox)==8 and sum(r['estimable'] for r in cox)==6
assert not any(r['signal']=='bgp' for r in cox)
target=ROOT/'deliverables/2026-10-28_COMMON_SAMPLE_MODELS.json'
assert not target.exists()
target.write_text(json.dumps(dict(scope='Exact three-signal common full-clean membership (254 events) for conditional recovery; common main integral matched membership (14 events) for dose. Original rows unchanged. Full-clean conditions on future completeness; not shared control windows or causal certification. No FE removal to recover dose estimates. All unavailable and absent signal specifications reported.',dose_models=dose,recovery_models=cox,recovery_risk=risk,not_emitted=[dict(signal='bgp',family='conditional_recovery',specifications=4,reason='No damaged-at-end BGP risk records in the common full-clean sample; no fitted effect, not zero effect.')]),indent=2,allow_nan=False)+'\n')
