#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
task_comparison=analysis/2026-10-24_past_only_comparison/v1/full_outputs
task_weather=analysis/2026-10-24_past_only_weather/v1/full_outputs
task_matching=analysis/2026-10-24_past_only_matching/v1/full_outputs
test ! -e "$task_comparison"
test ! -e "$task_weather"
test ! -e "$task_matching"
nice -n 10 "$task_python" -m scripts.run_past_only_comparison \
 --preflight analysis/2026-10-08_analysis_preflight/outputs --candidate analysis/2026-10-08_candidate_gate/outputs \
 --connection analysis/2026-10-07_event_inputs/connection_10min --quality analysis/2026-10-07_parallel_prep/ioda \
 --heat analysis/2026-10-07_event_inputs/heat_catalogue --stop analysis/2026-10-12_stop_windows/v2/outputs \
 --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs \
 --calendar-dir analysis/2026-10-12_control_calendar/v1/full_outputs \
 --baseline analysis/2026-10-24_past_only_baseline/v1/full_outputs --output "$task_comparison"
nice -n 10 "$task_python" outputs/2026-10-24_verify_stop_comparison.py \
 --verifier outputs/2026-10-12/verify_comparison_windows.py --output "$task_comparison" \
 --baseline analysis/2026-10-24_past_only_baseline/v1/full_outputs \
 --calendar analysis/2026-10-12_control_calendar/v1/full_outputs --heat analysis/2026-10-07_event_inputs/heat_catalogue \
 > "$task_comparison.verify.json"
nice -n 10 "$task_python" -m scripts.run_pre_weather --comparison "$task_comparison" \
 --heat analysis/2026-10-07_event_inputs/heat_catalogue --weather analysis/2026-10-06_era5_existing_data/country_daily --output "$task_weather"
nice -n 10 "$task_python" outputs/2026-10-12/verify_pre_weather.py "$task_weather" > "$task_weather.verify.json"
nice -n 10 "$task_python" -m scripts.run_variant_matching --comparison "$task_comparison" --weather "$task_weather" \
 --design docs/superpowers/specs/2026-10-12-matching-design.md --output "$task_matching"
nice -n 10 "$task_python" outputs/2026-10-12/verify_matching.py "$task_matching" > "$task_matching.verify.json"
echo "Verified past-only comparison weather and matching"
