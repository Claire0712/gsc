#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for scenario in unknown_end_plusminus7 unknown_end_plusminus30; do
 task_responses=analysis/2026-10-24_stop_reference_responses/v1/full_$scenario
 test -s "$task_responses.verify.json"
 for signal in ping-slash24 bgp merit-nt; do
  task_id=${scenario}_${signal}
  nice -n 10 "$task_python" -m scripts.run_variant_event_curve \
   --responses "$task_responses" --weather analysis/2026-10-24_stop_reference_weather/v1/full_$scenario \
   --matching analysis/2026-10-24_stop_reference_matching/v1/full_$scenario \
   --signal "$signal" --output analysis/2026-10-24_stop_reference_daily/v1/$task_id
  nice -n 10 "$task_python" outputs/2026-10-12/verify_event_curve.py \
   analysis/2026-10-24_stop_reference_daily/v1/$task_id > analysis/2026-10-24_stop_reference_responses/v1/$task_id.daily.verify.json
  nice -n 10 "$task_python" -m scripts.run_variant_hour_curve \
   --daily analysis/2026-10-24_stop_reference_daily/v1/$task_id --responses "$task_responses" \
   --output analysis/2026-10-24_stop_reference_hour/v1/$task_id
  nice -n 10 "$task_python" -m scripts.run_curve_inference \
   --estimates analysis/2026-10-24_stop_reference_hour/v1/$task_id \
   --output analysis/2026-10-24_stop_reference_inference/v1/$task_id
  nice -n 10 "$task_python" outputs/2026-10-12/verify_curve_inference.py \
   analysis/2026-10-24_stop_reference_inference/v1/$task_id > analysis/2026-10-24_stop_reference_responses/v1/$task_id.inference.verify.json
  nice -n 10 "$task_python" -m scripts.run_wild_coefficients \
   --inference analysis/2026-10-24_stop_reference_inference/v1/$task_id \
   --output analysis/2026-10-24_stop_reference_wild/v1/$task_id
  nice -n 10 "$task_python" outputs/2026-10-12/verify_wild_coefficients.py \
   analysis/2026-10-24_stop_reference_wild/v1/$task_id > analysis/2026-10-24_stop_reference_responses/v1/$task_id.wild.verify.json
  echo "Verified full-reference scenario curve $task_id"
 done
done
