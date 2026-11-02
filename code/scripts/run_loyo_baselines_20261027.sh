#!/bin/sh
# Unchanged baseline estimator/audit on each independently screened LOYO cohort.
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in "$@"; do
 case "$variant" in omit_2018|omit_2019|omit_2020|omit_2021) ;; *) exit 2 ;; esac
 task_heat=analysis/2026-10-27_loyo_heat_stage/v2/$variant
 task_preflight=analysis/2026-10-27_loyo_preflight/v1/$variant
 task_candidate=analysis/2026-10-27_loyo_candidate/v1/$variant
 task_output=analysis/2026-10-27_loyo_baseline/v1/full_$variant
 test -s analysis/2026-10-27_loyo_annual/v1/$variant/annual_event_screen.csv
 test ! -e "$task_output"
 nice -n10 "$task_python" -m scripts.run_connection_baseline \
  --preflight "$task_preflight" --candidate "$task_candidate" \
  --connection analysis/2026-10-07_event_inputs/connection_10min \
  --quality analysis/2026-10-07_parallel_prep/ioda --heat "$task_heat" \
  --stop analysis/2026-10-12_stop_windows/v2/outputs \
  --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs --output "$task_output"
 nice -n10 "$task_python" -m scripts.verify_variant_baseline_full \
  --project /volume1/homes/Judy/GSC2027/HeatSignal --output "$task_output" \
  --heat "$task_heat" --candidate "$task_candidate" --preflight "$task_preflight" \
  > "$task_output.verify.json"
 echo "Verified LOYO baseline $variant"
done
