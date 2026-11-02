#!/bin/sh
# Five alternatives; primary 300/24 remains immutable and is not rerun.
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for scenario in 100_24 500_24 100_72 300_72 500_72; do
 task_radius=${scenario%_*}
 task_hours=${scenario#*_}
 task_output=analysis/2026-10-25_cyclone_baseline/v1/full_$scenario
 test ! -e "$task_output"
 task_start=$(date +%s)
 nice -n10 "$task_python" -m scripts.run_cyclone_sensitivity_baseline \
  --preflight analysis/2026-10-08_analysis_preflight/outputs \
  --candidate analysis/2026-10-08_candidate_gate/outputs \
  --connection analysis/2026-10-07_event_inputs/connection_10min \
  --quality analysis/2026-10-07_parallel_prep/ioda \
  --heat analysis/2026-10-07_event_inputs/heat_catalogue \
  --stop analysis/2026-10-12_stop_windows/v2/outputs \
  --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs \
  --cyclone-radius "$task_radius" --cyclone-hours "$task_hours" --output "$task_output"
 task_end=$(date +%s)
 echo "Production seconds $scenario $((task_end-task_start))"
 nice -n10 "$task_python" -m scripts.verify_cyclone_sensitivity_baseline \
  --project /volume1/homes/Judy/GSC2027/HeatSignal --output "$task_output" \
  --heat analysis/2026-10-07_event_inputs/heat_catalogue \
  --candidate analysis/2026-10-08_candidate_gate/outputs \
  --preflight analysis/2026-10-08_analysis_preflight/outputs \
  --cyclone-radius "$task_radius" --cyclone-hours "$task_hours" \
  > "$task_output.verify.json"
 echo "Verified cyclone baseline $scenario"
done
