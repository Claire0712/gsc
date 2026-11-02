#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
ROOT=analysis/2026-10-30_solar_day/v1
"$PY" -c 'import json;from pathlib import Path;p=Path("analysis/2026-10-30_solar_day/v1");assert json.loads((p/"full_202401.verify.json").read_text())["status"]=="verified";assert json.loads((p/"full_202401.utc.verify.json").read_text())["status"]=="verified"'
months=$("$PY" -c 'print(" ".join(str(y)+str(m).zfill(2) for y in range(2018,2026) for m in range(1,13) if (y,m)!=(2024,1)))')
for month in $months; do test ! -e "$ROOT/full_$month"; done
for month in $months; do
 "$PY" -m scripts.run_solar_month --month "$month" --output "$ROOT/full_$month"
 "$PY" outputs/2026-10-30_verify_solar_tile.py "$ROOT/full_$month"
 "$PY" outputs/2026-10-30_verify_solar_month_utc.py "$ROOT/full_$month"
done
