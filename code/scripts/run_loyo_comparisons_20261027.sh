#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in "$@"; do
 case "$variant" in omit_2018|omit_2019|omit_2020|omit_2021) ;; *) exit 2 ;; esac
 task_output=analysis/2026-10-27_loyo_comparison/v1/full_$variant
 task_baseline=analysis/2026-10-27_loyo_baseline/v1/full_$variant
 task_calendar=analysis/2026-10-27_loyo_calendar/v1/full_$variant
 task_heat=analysis/2026-10-27_loyo_heat_stage/v2/$variant
 test ! -e "$task_output"
 test -s "$task_baseline.verify.json"
 if test "$variant" = omit_2018; then test -s "$task_calendar.verify_v2.json"; else test -s "$task_calendar.verify.json"; fi
 nice -n10 "$task_python" -m scripts.run_comparison_windows \
  --preflight analysis/2026-10-27_loyo_preflight/v1/$variant \
  --candidate analysis/2026-10-27_loyo_candidate/v1/$variant \
  --connection analysis/2026-10-07_event_inputs/connection_10min \
  --quality analysis/2026-10-07_parallel_prep/ioda --heat "$task_heat" \
  --stop analysis/2026-10-12_stop_windows/v2/outputs \
  --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs \
  --calendar-dir "$task_calendar" --baseline "$task_baseline" --output "$task_output"
 nice -n10 "$task_python" outputs/2026-10-22_verify_variant_comparison.py \
  --verifier outputs/2026-10-12/verify_comparison_windows.py \
  --output "$task_output" --baseline "$task_baseline" \
  --calendar "$task_calendar" --heat "$task_heat" > "$task_output.verify.json"
 echo "Verified LOYO comparison $variant"
done
