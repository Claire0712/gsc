#!/bin/sh
# Existing estimators and independent audits, all four preselected reference omissions.
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in omit_2018 omit_2019 omit_2020 omit_2021; do
 task_panel=analysis/2026-10-28_loyo_panel/v1/full_$variant
 task_metrics=analysis/2026-10-27_loyo_metrics/v1/full_$variant
 task_baseline=analysis/2026-10-27_loyo_baseline/v1/full_$variant
 task_matching=analysis/2026-10-27_loyo_matching/v1/full_$variant
 task_associations=analysis/2026-10-28_loyo_associations/v1/full_$variant
 task_qualified=analysis/2026-10-28_loyo_recovery_qualification/v1/full_$variant
 task_cox=analysis/2026-10-28_loyo_recovery_cox/v2/full_$variant
 test -s "$task_matching.verify.json"
 test -s "$task_metrics.verify.json"
 test ! -e "$task_panel"
 test ! -e "$task_associations"
 test ! -e "$task_qualified"
 test ! -e "$task_cox"
 nice -n10 "$task_python" -m scripts.run_event_panel \
  --metrics "$task_metrics" --matching "$task_matching" \
  --catalogue analysis/2026-10-27_loyo_heat_stage/v2/$variant --output "$task_panel"
 "$task_python" outputs/2026-10-13/verify_event_panel.py "$task_panel" > "$task_panel.verify.json"
 nice -n10 "$task_python" -m scripts.run_heat_associations_v2 --panel "$task_panel" --output "$task_associations"
 "$task_python" outputs/2026-10-13/verify_heat_associations.py "$task_associations" > "$task_associations.verify.json"
 nice -n10 "$task_python" -m scripts.run_variant_recovery_qualification \
  --panel "$task_panel" --metrics "$task_metrics" --baseline "$task_baseline" --output "$task_qualified"
 "$task_python" outputs/2026-10-15_verify_recovery_qualification.py "$task_qualified" > "$task_qualified.verify.json"
 nice -n10 "$task_python" -m scripts.run_recovery_cox_v2 --qualified "$task_qualified" --output "$task_cox"
 "$task_python" outputs/2026-10-22_verify_recovery_cox_v2.py "$task_cox" > "$task_cox.verify.json"
 echo "Verified LOYO dose and recovery models $variant"
done
