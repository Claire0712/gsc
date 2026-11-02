#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
ROOT=analysis/2026-10-30_calendar_blocks/v1
"$PY" -c 'import json;from pathlib import Path;p=Path("analysis/2026-10-30_calendar_blocks/v1");assert json.loads((p/"pilot_bgp_plus28.stack.verify.json").read_text())["status"]=="verified";assert json.loads((p/"pilot_bgp_plus28.point.verify.json").read_text())["status"]=="verified"'
for key in minus56 minus28 plus28 plus56; do test ! -e "$ROOT/full_$key"; done
for days in -56 -28 28 56; do
 case "$days" in -56) key=minus56;; -28) key=minus28;; 28) key=plus28;; 56) key=plus56;; esac
 "$PY" -m scripts.run_calendar_block_placebo --base analysis/2026-10-12_event_curve/v1 --output "$ROOT/full_$key" --shift "$days"
 "$PY" outputs/2026-10-30_verify_calendar_blocks.py "$ROOT/full_$key"
 for signal in ping-slash24 bgp merit-nt; do
  estimate="$ROOT/full_$key/$signal"
  if [ ! -f "$estimate/manifest.json" ]; then continue; fi
  "$PY" outputs/verify_precip_curve_point.py "$estimate" > "$ROOT/${key}_${signal}.point.verify.json"
  "$PY" -m scripts.run_curve_inference --estimates "$estimate" --output "$ROOT/${key}_${signal}_inference"
  "$PY" outputs/2026-10-12/verify_curve_inference.py "$ROOT/${key}_${signal}_inference" > "$ROOT/${key}_${signal}.inference.verify.json"
  "$PY" -m scripts.run_wild_coefficients --inference "$ROOT/${key}_${signal}_inference" --output "$ROOT/${key}_${signal}_wild"
  "$PY" outputs/2026-10-12/verify_wild_coefficients.py "$ROOT/${key}_${signal}_wild" > "$ROOT/${key}_${signal}.wild.verify.json"
 done
done
