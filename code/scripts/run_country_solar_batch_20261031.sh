#!/bin/bash
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
py_exec=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
base=analysis/2026-10-31_country_solar/v1
if [ -f "$base/full_batch.pid" ] && kill -0 "$(cat "$base/full_batch.pid")" 2>/dev/null; then exit 2; fi
echo $$ > "$base/full_batch.pid"
# The complete preselected month must pass both independent gates first.
"$py_exec" -c 'import json,hashlib;from pathlib import Path;p=Path("analysis/2026-10-31_country_solar/v1/full_202401");h=hashlib.sha256((p/"manifest.json").read_bytes()).hexdigest();assert all(json.loads(p.with_name(p.name+s).read_text())["manifest_sha256"]==h for s in (".verify.json",".utc.verify.json"))'
for year in 2018 2019 2020 2021 2022 2023 2024 2025; do
 for month in 01 02 03 04 05 06 07 08 09 10 11 12; do
  target="$base/full_$year$month"
  if [ -d "$target" ]; then
   "$py_exec" -c 'from pathlib import Path;import json,sys;p=Path(sys.argv[1]);assert json.loads((p/"status.json").read_text())["status"]=="completed"' "$target"
  else
   "$py_exec" -m scripts.run_country_solar_month_20261031 --month "$year$month" --output "$target"
  fi
  if [ ! -f "$target.verify.json" ] || [ ! -f "$target.utc.verify.json" ]; then
   "$py_exec" outputs/2026-10-31_verify_country_solar_month.py "$target"
  fi
  "$py_exec" -c 'from pathlib import Path;import json,hashlib,sys;p=Path(sys.argv[1]);h=hashlib.sha256((p/"manifest.json").read_bytes()).hexdigest();assert all(json.loads(p.with_name(p.name+s).read_text())["status"]=="verified" and json.loads(p.with_name(p.name+s).read_text())["manifest_sha256"]==h for s in (".verify.json",".utc.verify.json"))' "$target"
 done
done
"$py_exec" -m scripts.run_country_solar_catalogue_20261031 --output analysis/2026-10-31_country_solar_catalogue/v1/full_outputs
"$py_exec" outputs/2026-10-31_verify_solar_catalogue.py analysis/2026-10-31_country_solar_catalogue/v1/full_outputs
"$py_exec" outputs/2026-10-31_verify_solar_event_bounds.py analysis/2026-10-31_country_solar_catalogue/v1/full_outputs
