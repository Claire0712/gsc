#!/bin/sh
# Existing tested baseline estimator with explicit hypothetical STOP windows.
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for scenario in unknown_end_plusminus7 unknown_end_plusminus30; do
 task_output=analysis/2026-10-23_stop_reference_baseline/v1/full_$scenario
 test ! -e "$task_output"
 nice -n 10 "$task_python" -m scripts.run_connection_baseline_stop_scenario \
  --preflight analysis/2026-10-08_analysis_preflight/outputs \
  --candidate analysis/2026-10-08_candidate_gate/outputs \
  --connection analysis/2026-10-07_event_inputs/connection_10min \
  --quality analysis/2026-10-07_parallel_prep/ioda \
  --heat analysis/2026-10-07_event_inputs/heat_catalogue \
  --stop analysis/2026-10-12_stop_windows/v2/outputs \
  --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs \
  --stop-scenario "$scenario" --output "$task_output"
 nice -n 10 "$task_python" -m scripts.verify_stop_scenario_baseline \
  --project /volume1/homes/Judy/GSC2027/HeatSignal --output "$task_output" \
  --heat analysis/2026-10-07_event_inputs/heat_catalogue \
  --candidate analysis/2026-10-08_candidate_gate/outputs \
  --preflight analysis/2026-10-08_analysis_preflight/outputs \
  --stop-scenario "$scenario" \
  > analysis/2026-10-23_stop_reference_baseline/v1/full_$scenario.verify.json
 echo "Verified reference baseline $scenario"
done
