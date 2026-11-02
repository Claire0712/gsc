#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for task_path in analysis/2026-10-24_country_sensitivity/v1/full_* analysis/2026-10-24_leave_country/v1/full_ap_A_M1; do
 if test -d "$task_path"; then
  test ! -e "$task_path.verify_v2.json"
  nice -n 10 "$task_python" outputs/2026-10-24_verify_country_sensitivity_v2.py "$task_path" > "$task_path.verify_v2.json"
  echo "Verified rank and CR0 $task_path"
 fi
done
