#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in "$@"; do
 case "$variant" in omit_2018|omit_2019|omit_2020|omit_2021) ;; *) exit 2 ;; esac
 task_comparison=analysis/2026-10-27_loyo_comparison/v1/full_$variant
 task_weather=analysis/2026-10-27_loyo_weather/v1/full_$variant
 task_matching=analysis/2026-10-27_loyo_matching/v1/full_$variant
 test -s "$task_comparison.verify.json"
 test ! -e "$task_weather"
 test ! -e "$task_matching"
 nice -n10 "$task_python" -m scripts.run_loyo_pre_weather \
  --comparison "$task_comparison" --heat analysis/2026-10-27_loyo_heat_stage/v2/$variant \
  --weather analysis/2026-10-06_era5_existing_data/country_daily \
  --batch analysis/2026-10-27_loyo_catalogues/v1/full_outputs/manifest.json \
  --source-heat analysis/2026-10-07_event_inputs/heat_catalogue/manifest.json --output "$task_weather"
 nice -n10 "$task_python" outputs/2026-10-12/verify_pre_weather.py "$task_weather" > "$task_weather.verify.json"
 nice -n10 "$task_python" -m scripts.run_variant_matching \
  --comparison "$task_comparison" --weather "$task_weather" \
  --design docs/superpowers/specs/2026-10-12-matching-design.md --output "$task_matching"
 nice -n10 "$task_python" outputs/2026-10-12/verify_matching.py "$task_matching" > "$task_matching.verify.json"
 echo "Verified LOYO weather and matching $variant"
done
