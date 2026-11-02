#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for universe in joint all; do
 task_output=analysis/2026-10-26_sync_baseline/v1/full_$universe
 test ! -e "$task_output"
 nice -n10 "$task_python" -m scripts.run_sync_baseline \
  --preflight analysis/2026-10-08_analysis_preflight/outputs \
  --candidate analysis/2026-10-08_candidate_gate/outputs \
  --connection analysis/2026-10-07_event_inputs/connection_10min \
  --quality analysis/2026-10-07_parallel_prep/ioda \
  --heat analysis/2026-10-07_event_inputs/heat_catalogue \
  --stop analysis/2026-10-12_stop_windows/v2/outputs \
  --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs \
  --sync analysis/2026-10-11_synchronous_screen/v3/full_outputs \
  --universe "$universe" --output "$task_output"
 nice -n10 "$task_python" -m scripts.verify_sync_baseline \
  --project /volume1/homes/Judy/GSC2027/HeatSignal --output "$task_output" \
  --heat analysis/2026-10-07_event_inputs/heat_catalogue \
  --candidate analysis/2026-10-08_candidate_gate/outputs \
  --preflight analysis/2026-10-08_analysis_preflight/outputs --universe "$universe" > "$task_output.verify.json"
 echo "Verified sync baseline $universe"
done
