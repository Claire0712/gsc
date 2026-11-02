#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in "$@"; do
 case "$variant" in omit_2018|omit_2019|omit_2020|omit_2021) ;; *) exit 2 ;; esac
 task_baseline=/volume1/homes/Judy/GSC2027/HeatSignal/analysis/2026-10-27_loyo_baseline/v1/full_$variant
 task_metrics=analysis/2026-10-27_loyo_metrics/v1/full_$variant
 task_calendar=analysis/2026-10-27_loyo_calendar/v1/full_$variant
 test -s "$task_baseline.verify.json"
 test ! -e "$task_metrics"
 test ! -e "$task_calendar"
 nice -n10 "$task_python" -m scripts.run_heat_resilience_metrics --baseline "$task_baseline" --output "$task_metrics"
 nice -n10 "$task_python" outputs/2026-10-12/verify_metrics_full.py \
  --baseline "$task_baseline" --metrics "$task_metrics" --output "$task_metrics.verify.json"
 nice -n10 "$task_python" -m scripts.build_control_calendar \
  --candidate analysis/2026-10-27_loyo_candidate/v1/$variant \
  --heat analysis/2026-10-27_loyo_heat_stage/v2/$variant --output "$task_calendar"
 nice -n10 "$task_python" outputs/2026-10-27_verify_loyo_calendar.py "$task_calendar" > "$task_calendar.verify.json"
 echo "Verified LOYO metrics and calendar $variant"
done
