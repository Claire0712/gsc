#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
nice -n 10 "$task_python" -m scripts.run_leave_country --panel analysis/2026-10-13_event_panel/v1/full_outputs \
 --output analysis/2026-10-24_leave_country/v1/full_ap_A_M1
nice -n 10 "$task_python" outputs/2026-10-24_verify_leave_country.py \
 analysis/2026-10-24_leave_country/v1/full_ap_A_M1 > analysis/2026-10-24_leave_country/v1/full_ap_A_M1.verify.json
echo "Verified primary AP A/M1 leave-country coefficient sensitivity"
