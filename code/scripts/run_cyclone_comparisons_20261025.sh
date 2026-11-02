#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for scenario in 100_24 500_24 100_72 300_72 500_72; do
 task_radius=${scenario%_*};task_hours=${scenario#*_}
 task_output=analysis/2026-10-25_cyclone_comparison/v1/full_$scenario
 task_baseline=analysis/2026-10-25_cyclone_baseline/v1/full_$scenario
 test ! -e "$task_output"
 nice -n 10 "$task_python" -m scripts.run_cyclone_comparison \
  --preflight analysis/2026-10-08_analysis_preflight/outputs \
  --candidate analysis/2026-10-08_candidate_gate/outputs \
  --connection analysis/2026-10-07_event_inputs/connection_10min \
  --quality analysis/2026-10-07_parallel_prep/ioda \
  --heat analysis/2026-10-07_event_inputs/heat_catalogue \
  --stop analysis/2026-10-12_stop_windows/v2/outputs \
  --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs \
  --calendar-dir analysis/2026-10-12_control_calendar/v1/full_outputs \
  --baseline "$task_baseline" --cyclone-radius "$task_radius" --cyclone-hours "$task_hours" --output "$task_output"
 nice -n 10 "$task_python" outputs/2026-10-24_verify_stop_comparison.py \
  --verifier outputs/2026-10-12/verify_comparison_windows.py \
  --output "$task_output" --baseline "$task_baseline" \
  --calendar analysis/2026-10-12_control_calendar/v1/full_outputs \
  --heat analysis/2026-10-07_event_inputs/heat_catalogue \
  > "$task_output.verify.json"
 nice -n 10 "$task_python" -m scripts.verify_cyclone_comparison_masks \
  --output "$task_output" --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs \
  > "$task_output.masks.json"
 echo "Verified cyclone comparison $scenario"
done
