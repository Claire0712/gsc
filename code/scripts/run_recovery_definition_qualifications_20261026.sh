#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for scenario in 90_4h 98_4h 95_2h 95_6h; do
 task_output=analysis/2026-10-26_recovery_qualification/v1/full_$scenario
 test ! -e "$task_output"
 nice -n10 "$task_python" -m scripts.run_recovery_definition_qualification \
  --panel analysis/2026-10-13_event_panel/v1/full_outputs \
  --baseline analysis/2026-10-12_connection_baseline/v1/full_outputs \
  --metrics analysis/2026-10-25_recovery_definition/v1/full_$scenario --output "$task_output"
 nice -n10 "$task_python" scripts/verify_recovery_definition_qualification.py "$task_output" > "$task_output.verify.json"
 echo "Verified recovery qualification $scenario"
done
