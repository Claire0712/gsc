#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in q95 min3; do
 for scenario in unknown_end_plusminus7 unknown_end_plusminus30; do
  task_key=${variant}_${scenario}
  for signal in ping-slash24 bgp merit-nt; do
   task_id=${task_key}_${signal}
   nice -n 10 "$task_python" -m scripts.run_variant_event_curve \
    --responses analysis/2026-10-23_stop_scenario_responses/v1/$task_key \
    --weather analysis/2026-10-22_variant_weather/v1/full_$variant \
    --matching analysis/2026-10-23_stop_scenario_matching/v1/$task_key \
    --signal "$signal" --output analysis/2026-10-23_stop_scenario_daily/v1/$task_id
   nice -n 10 "$task_python" outputs/2026-10-12/verify_event_curve.py \
    analysis/2026-10-23_stop_scenario_daily/v1/$task_id \
    > analysis/2026-10-23_stop_scenario_matching/v1/$task_id.daily.verify.json
   nice -n 10 "$task_python" -m scripts.run_variant_hour_curve \
    --daily analysis/2026-10-23_stop_scenario_daily/v1/$task_id \
    --responses analysis/2026-10-23_stop_scenario_responses/v1/$task_key \
    --output analysis/2026-10-23_stop_scenario_hour/v1/$task_id
   nice -n 10 "$task_python" -m scripts.run_curve_inference \
    --estimates analysis/2026-10-23_stop_scenario_hour/v1/$task_id \
    --output analysis/2026-10-23_stop_scenario_inference/v1/$task_id
   nice -n 10 "$task_python" outputs/2026-10-12/verify_curve_inference.py \
    analysis/2026-10-23_stop_scenario_inference/v1/$task_id \
    > analysis/2026-10-23_stop_scenario_matching/v1/$task_id.inference.verify.json
   nice -n 10 "$task_python" -m scripts.run_wild_coefficients \
    --inference analysis/2026-10-23_stop_scenario_inference/v1/$task_id \
    --output analysis/2026-10-23_stop_scenario_wild/v1/$task_id
   nice -n 10 "$task_python" outputs/2026-10-12/verify_wild_coefficients.py \
    analysis/2026-10-23_stop_scenario_wild/v1/$task_id \
    > analysis/2026-10-23_stop_scenario_matching/v1/$task_id.wild.verify.json
   echo "Verified changed scenario curve $task_id"
  done
 done
done
