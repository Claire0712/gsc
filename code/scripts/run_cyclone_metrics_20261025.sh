#!/bin/sh
# Unchanged metrics estimator and independent representative-state audit.
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for scenario in 100_24 500_24 100_72 300_72 500_72; do
 task_baseline=/volume1/homes/Judy/GSC2027/HeatSignal/analysis/2026-10-25_cyclone_baseline/v1/full_$scenario
 task_output=analysis/2026-10-25_cyclone_metrics/v1/full_$scenario
 test -s "$task_baseline.verify.json"
 test ! -e "$task_output"
 nice -n10 "$task_python" -m scripts.run_heat_resilience_metrics --baseline "$task_baseline" --output "$task_output"
 nice -n10 "$task_python" outputs/2026-10-12/verify_metrics_full.py \
  --baseline "$task_baseline" --metrics "$task_output" --output "$task_output.verify.json"
 echo "Verified cyclone metrics $scenario"
done
