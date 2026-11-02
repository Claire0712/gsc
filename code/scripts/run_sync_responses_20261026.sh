#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for scenario in "$@"; do
 case "$scenario" in joint|all) ;; *) exit 2 ;; esac
 task_comparison=analysis/2026-10-26_sync_comparison/v1/full_$scenario
 task_weather=analysis/2026-10-26_sync_weather/v1/full_$scenario
 task_matching=analysis/2026-10-26_sync_matching/v1/full_$scenario
 task_measurement=analysis/2026-10-26_sync_measurement/v1/full_$scenario
 task_stop=analysis/2026-10-26_sync_review/v1/full_$scenario
 task_responses=analysis/2026-10-26_sync_responses/v1/full_$scenario
 test -s "$task_matching.verify.json"
 nice -n 10 "$task_python" -m scripts.run_measurement_review --comparison "$task_comparison" \
  --sync analysis/2026-10-11_synchronous_screen/v3/full_outputs --evidence outputs/2026-10-11 --output "$task_measurement"
 nice -n 10 "$task_python" outputs/2026-10-12/verify_measurement_review.py "$task_measurement" > "$task_measurement.verify.json"
 nice -n 10 "$task_python" -m scripts.run_variant_stop_window_review --comparison "$task_comparison" \
  --weather "$task_weather" --stop analysis/2026-10-12_stop_windows/v2/outputs \
  --matching "$task_matching" --output "$task_stop"
 nice -n 10 "$task_python" outputs/2026-10-12/verify_stop_review.py "$task_stop" > "$task_stop.verify.json"
 nice -n 10 "$task_python" -m scripts.run_variant_paired_responses_v2 --comparison "$task_comparison" \
  --matching "$task_matching" --measurement "$task_measurement" --stop-review "$task_stop" \
  --design docs/superpowers/specs/2026-10-12-matching-design.md --output "$task_responses"
 nice -n 10 "$task_python" outputs/2026-10-12/verify_paired_responses.py "$task_responses" > "$task_responses.verify.json"
 echo "Verified sync responses $scenario"
done
