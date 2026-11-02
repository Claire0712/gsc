#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for scenario in unknown_end_plusminus7 unknown_end_plusminus30; do
 task_baseline=analysis/2026-10-23_stop_reference_baseline/v1/full_$scenario
 task_output=analysis/2026-10-23_stop_reference_metrics/v1/full_$scenario
 nice -n 10 "$task_python" -m scripts.run_heat_resilience_metrics --baseline "$task_baseline" --output "$task_output"
 nice -n 10 "$task_python" outputs/2026-10-12/verify_metrics_full.py --baseline "/volume1/homes/Judy/GSC2027/HeatSignal/$task_baseline" --metrics "$task_output" --output analysis/2026-10-23_stop_reference_metrics/v1/full_$scenario.verify.json
 echo "Verified reference metrics $scenario"
done
