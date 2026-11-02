#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
nice -n 10 "$task_python" -m scripts.run_heat_resilience_metrics \
 --baseline analysis/2026-10-24_past_only_baseline/v1/full_outputs \
 --output analysis/2026-10-24_past_only_metrics/v1/full_outputs
nice -n 10 "$task_python" outputs/2026-10-12/verify_metrics_full.py \
 --baseline /volume1/homes/Judy/GSC2027/HeatSignal/analysis/2026-10-24_past_only_baseline/v1/full_outputs \
 --metrics analysis/2026-10-24_past_only_metrics/v1/full_outputs \
 --output analysis/2026-10-24_past_only_metrics/v1/full_outputs.verify.json
nice -n 10 "$task_python" -m scripts.run_past_only_comparison \
 --preflight analysis/2026-10-08_analysis_preflight/outputs --candidate analysis/2026-10-08_candidate_gate/outputs \
 --connection analysis/2026-10-07_event_inputs/connection_10min --quality analysis/2026-10-07_parallel_prep/ioda \
 --heat analysis/2026-10-07_event_inputs/heat_catalogue --stop analysis/2026-10-12_stop_windows/v2/outputs \
 --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs \
 --calendar-dir analysis/2026-10-12_control_calendar/v1/full_outputs \
 --baseline analysis/2026-10-24_past_only_baseline/v1/full_outputs \
 --countries MYS --signals ping-slash24 --output analysis/2026-10-24_past_only_comparison/v1/pilot_mys_ap
