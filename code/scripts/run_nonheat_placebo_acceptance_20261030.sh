#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
ROOT=analysis/2026-10-29_nonheat_placebo/v1
"$PY" -c 'import json;from pathlib import Path;assert json.loads(Path("analysis/2026-10-29_nonheat_placebo/v1/full_outputs/status.json").read_text())["status"]=="completed";assert json.loads(Path("analysis/2026-10-29_nonheat_placebo/v1/full_outputs.stack.verify.json").read_text())["status"]=="verified"'
for signal in ping-slash24 bgp merit-nt; do
 estimates="$ROOT/full_outputs/$signal"
 if [ ! -f "$estimates/manifest.json" ]; then
  "$PY" -c 'import json,sys;from pathlib import Path;d=json.loads((Path(sys.argv[1])/"status.json").read_text());assert d["status"]=="not_estimable";print(d)' "$estimates"
  continue
 fi
 "$PY" outputs/verify_precip_curve_point.py "$estimates" > "$ROOT/$signal.point.verify.json"
 "$PY" -m scripts.run_curve_inference --estimates "$estimates" --output "$ROOT/${signal}_inference"
 "$PY" outputs/2026-10-12/verify_curve_inference.py "$ROOT/${signal}_inference" > "$ROOT/$signal.inference.verify.json"
 "$PY" -m scripts.run_wild_coefficients --inference "$ROOT/${signal}_inference" --output "$ROOT/${signal}_wild"
 "$PY" outputs/2026-10-12/verify_wild_coefficients.py "$ROOT/${signal}_wild" > "$ROOT/$signal.wild.verify.json"
done
