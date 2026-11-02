#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
task_baseline=/volume1/homes/Judy/GSC2027/HeatSignal/analysis/2026-10-12_connection_baseline/v1/full_outputs
for scenario in 90_4h 98_4h 95_2h 95_6h; do
 case "$scenario" in
  90_4h) threshold=.9;slots=24;;98_4h) threshold=.98;slots=24;;
  95_2h) threshold=.95;slots=12;;95_6h) threshold=.95;slots=36;;
 esac
 task_output=analysis/2026-10-25_recovery_definition/v1/full_$scenario
 test ! -e "$task_output"
 nice -n10 "$task_python" -m scripts.run_recovery_definition_metrics \
  --baseline "$task_baseline" --output "$task_output" \
  --maintenance-threshold "$threshold" --confirmation-slots "$slots"
 nice -n10 "$task_python" scripts/verify_recovery_definition_metrics.py \
  --baseline "$task_baseline" --metrics "$task_output" --output "$task_output.verify.json"
 echo "Verified recovery definition $scenario"
done
