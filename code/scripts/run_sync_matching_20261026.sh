#!/bin/sh
# Compose existing verified weather and matching estimators; no new algorithm.
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for scenario in "$@"; do
 case "$scenario" in joint|all) ;; *) exit 2 ;; esac
 task_comparison=analysis/2026-10-26_sync_comparison/v1/full_$scenario
 task_weather=analysis/2026-10-26_sync_weather/v1/full_$scenario
 task_matching=analysis/2026-10-26_sync_matching/v1/full_$scenario
 test -s "$task_comparison.verify.json"
 test ! -e "$task_weather"
 test ! -e "$task_matching"
 nice -n 10 "$task_python" -m scripts.run_pre_weather \
  --comparison "$task_comparison" --heat analysis/2026-10-07_event_inputs/heat_catalogue \
  --weather analysis/2026-10-06_era5_existing_data/country_daily --output "$task_weather"
 nice -n 10 "$task_python" outputs/2026-10-12/verify_pre_weather.py "$task_weather" > "$task_weather.verify.json"
 nice -n 10 "$task_python" -m scripts.run_variant_matching \
  --comparison "$task_comparison" --weather "$task_weather" \
  --design docs/superpowers/specs/2026-10-12-matching-design.md --output "$task_matching"
 nice -n 10 "$task_python" outputs/2026-10-12/verify_matching.py "$task_matching" > "$task_matching.verify.json"
 echo "Verified sync weather and matching $scenario"
done
