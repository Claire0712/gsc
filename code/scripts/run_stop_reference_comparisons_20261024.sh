#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for scenario in unknown_end_plusminus7 unknown_end_plusminus30; do
 task_output=analysis/2026-10-24_stop_reference_comparison/v1/full_$scenario
 task_baseline=analysis/2026-10-23_stop_reference_baseline/v1/full_$scenario
 test ! -e "$task_output"
 nice -n 10 "$task_python" -m scripts.run_stop_scenario_comparison \
  --preflight analysis/2026-10-08_analysis_preflight/outputs \
  --candidate analysis/2026-10-08_candidate_gate/outputs \
  --connection analysis/2026-10-07_event_inputs/connection_10min \
  --quality analysis/2026-10-07_parallel_prep/ioda \
  --heat analysis/2026-10-07_event_inputs/heat_catalogue \
  --stop analysis/2026-10-12_stop_windows/v2/outputs \
  --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs \
  --calendar-dir analysis/2026-10-12_control_calendar/v1/full_outputs \
  --baseline "$task_baseline" --stop-scenario "$scenario" --output "$task_output"
 nice -n 10 "$task_python" outputs/2026-10-24_verify_stop_comparison.py \
  --verifier outputs/2026-10-12/verify_comparison_windows.py \
  --output "$task_output" --baseline "$task_baseline" \
  --calendar analysis/2026-10-12_control_calendar/v1/full_outputs \
  --heat analysis/2026-10-07_event_inputs/heat_catalogue \
  > "$task_output.verify.json"
 echo "Verified remasked comparison $scenario"
done
