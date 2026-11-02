#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for scenario in 90_4h 98_4h 95_2h 95_6h; do
 task_qualified=analysis/2026-10-26_recovery_qualification/v1/full_$scenario
 task_output=analysis/2026-10-26_recovery_cox/v1/full_$scenario
 test -s "$task_qualified.verify.json"
 test ! -e "$task_output"
 nice -n10 "$task_python" -m scripts.run_recovery_cox_v2 --qualified "$task_qualified" --output "$task_output"
 nice -n10 "$task_python" outputs/2026-10-22_verify_recovery_cox_v2.py "$task_output" > "$task_output.verify.json"
 echo "Verified recovery definition Cox $scenario"
done
