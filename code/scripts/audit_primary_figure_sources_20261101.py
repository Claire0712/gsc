"""Check preserved primary Cox numerical objects against independently verified refits."""
from pathlib import Path
import hashlib,json,numpy as np
root=Path.cwd();old=root/'analysis/2026-10-15_recovery_cox/v1/full_outputs';new=root/'analysis/2026-10-30_cox_health/v1/full_outputs';h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def product(p,name):
 m=json.loads((p/'manifest.json').read_text());assert h(p/name)==m['outputs'][name]['sha256'];return json.loads((p/name).read_text())
a=product(old,'results.json');b=product(new,'results.json');fits=product(new,'diagnostic_fits.json');audit=json.loads(new.with_name('full_outputs.verify.json').read_text());assert audit['status']=='verified' and audit['manifest_sha256']==h(new/'manifest.json');lookup={tuple(r[k] for k in ('signal','sample','model')):r for r in a};flookup={tuple(f['identity']):f for f in fits};checked=0;maximum=0
for r in b:
 key=tuple(r[k] for k in ('signal','sample','model'));previous=lookup[key];assert previous['estimable']==r['decisions']['main']
 if not r['decisions']['main']:continue
 assert previous['terms']==r['terms'];np.testing.assert_allclose(previous['beta_per_original_unit'],r['beta_per_original_unit'],rtol=0,atol=1e-10);matrix=old/previous['matrix'];m=json.loads((old/'manifest.json').read_text());assert h(matrix)==m['outputs'][matrix.name]['sha256'];z=np.load(matrix);f=flookup[key]
 for name in ('z','t','d','beta','cov'):
  x=np.array(f[name]);np.testing.assert_allclose(z[name],x,atol=1e-10,rtol=1e-10);maximum=max(maximum,float(np.max(np.abs(z[name]-x))))
 scale=z['scale'];beta=np.asarray(f['beta'])/scale;se=np.sqrt(np.diag(f['cov']))/scale;ci=np.exp(np.column_stack([beta-1.959963984540054*se,beta+1.959963984540054*se]));np.testing.assert_allclose(ci,previous['hazard_ratio95'],rtol=1e-9,atol=1e-10);checked+=1
assert checked==8
result=dict(status='verified',models_checked=len(b),accepted_models_with_risk_arrays_beta_cov_and_CI_equivalence=checked,max_array_difference=maximum,old_manifest_sha256=h(old/'manifest.json'),independently_verified_current_refit_manifest_sha256=h(new/'manifest.json'),source_risk_set_manifest='analysis/2026-10-22_main_recovery_cox/v2/full_outputs/manifest.json',scope='Numerical equivalence permits preserved primary figure objects to be reused; no model refit or broader inference/PH certificate.')
out=root/'outputs/2026-11-01_primary_figure_source_linkage.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
