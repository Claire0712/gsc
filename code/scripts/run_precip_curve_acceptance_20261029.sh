#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
ROOT=analysis/2026-10-29_precip_curve/v1
"$PY" -c 'import json;from pathlib import Path;assert json.loads(Path("analysis/2026-10-29_precip_curve/v1/full_outputs/status.json").read_text())["status"]=="completed"'
"$PY" outputs/2026-10-29_verify_precip_curve_stack.py "$ROOT/full_outputs"
for signal in ping-slash24 bgp merit-nt; do
 for model in base precip; do
  estimates="$ROOT/full_outputs/${signal}_$model"
  if [ ! -f "$estimates/manifest.json" ]; then
   "$PY" -c 'import json,sys;from pathlib import Path;d=json.loads((Path(sys.argv[1])/"status.json").read_text());assert d["status"]=="not_estimable";print(d)' "$estimates"
   continue
  fi
  "$PY" outputs/verify_precip_curve_point.py "$estimates" > "$ROOT/${signal}_${model}.point.verify.json"
  "$PY" -m scripts.run_curve_inference --estimates "$estimates" --output "$ROOT/${signal}_${model}_inference"
  "$PY" outputs/2026-10-12/verify_curve_inference.py "$ROOT/${signal}_${model}_inference" > "$ROOT/${signal}_${model}.inference.verify.json"
  "$PY" -m scripts.run_wild_coefficients --inference "$ROOT/${signal}_${model}_inference" --output "$ROOT/${signal}_${model}_wild"
  "$PY" outputs/2026-10-12/verify_wild_coefficients.py "$ROOT/${signal}_${model}_wild" > "$ROOT/${signal}_${model}.wild.verify.json"
 done
done
