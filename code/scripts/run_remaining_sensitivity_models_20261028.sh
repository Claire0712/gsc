#!/bin/sh
# Existing models on previously verified alternative baseline/exclusion stages.
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for key in cyclone_100_24 cyclone_500_24 cyclone_100_72 cyclone_300_72 cyclone_500_72 stop_7 stop_30 sync_joint sync_all past_only; do
 case "$key" in
  cyclone_*) scenario=${key#cyclone_}; task_baseline=analysis/2026-10-25_cyclone_baseline/v1/full_$scenario; task_metrics=analysis/2026-10-25_cyclone_metrics/v1/full_$scenario; task_matching=analysis/2026-10-25_cyclone_matching/v1/full_$scenario ;;
  stop_*) days=${key#stop_}; scenario=unknown_end_plusminus$days; task_baseline=analysis/2026-10-23_stop_reference_baseline/v1/full_$scenario; task_metrics=analysis/2026-10-23_stop_reference_metrics/v1/full_$scenario; task_matching=analysis/2026-10-24_stop_reference_matching/v1/full_$scenario ;;
  sync_*) scenario=${key#sync_}; task_baseline=analysis/2026-10-26_sync_baseline/v1/full_$scenario; task_metrics=analysis/2026-10-26_sync_metrics/v1/full_$scenario; task_matching=analysis/2026-10-26_sync_matching/v1/full_$scenario ;;
  past_only) task_baseline=analysis/2026-10-24_past_only_baseline/v1/full_outputs; task_metrics=analysis/2026-10-24_past_only_metrics/v1/full_outputs; task_matching=analysis/2026-10-24_past_only_matching/v1/full_outputs ;;
 esac
 task_panel=analysis/2026-10-28_sensitivity_panel/v1/$key
 task_associations=analysis/2026-10-28_sensitivity_associations/v1/$key
 task_qualified=analysis/2026-10-28_sensitivity_qualification/v1/$key
 task_cox=analysis/2026-10-28_sensitivity_cox/v2/$key
 test -s "$task_metrics.verify.json"
 test -s "$task_matching.verify.json"
 test ! -e "$task_panel"
 test ! -e "$task_associations"
 test ! -e "$task_qualified"
 test ! -e "$task_cox"
 nice -n10 "$task_python" -m scripts.run_event_panel --metrics "$task_metrics" --matching "$task_matching" \
  --catalogue analysis/2026-10-07_event_inputs/heat_catalogue --output "$task_panel"
 "$task_python" outputs/2026-10-13/verify_event_panel.py "$task_panel" > "$task_panel.verify.json"
 nice -n10 "$task_python" -m scripts.run_heat_associations_v2 --panel "$task_panel" --output "$task_associations"
 "$task_python" outputs/2026-10-13/verify_heat_associations.py "$task_associations" > "$task_associations.verify.json"
 nice -n10 "$task_python" -m scripts.run_variant_recovery_qualification --panel "$task_panel" \
  --metrics "$task_metrics" --baseline "$task_baseline" --output "$task_qualified"
 "$task_python" outputs/2026-10-15_verify_recovery_qualification.py "$task_qualified" > "$task_qualified.verify.json"
 nice -n10 "$task_python" -m scripts.run_recovery_cox_v2 --qualified "$task_qualified" --output "$task_cox"
 "$task_python" outputs/2026-10-22_verify_recovery_cox_v2.py "$task_cox" > "$task_cox.verify.json"
 echo "Verified remaining sensitivity models $key"
done
