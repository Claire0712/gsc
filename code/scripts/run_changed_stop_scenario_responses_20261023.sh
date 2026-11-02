#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in q95 min3; do
  for scenario in unknown_end_plusminus7 unknown_end_plusminus30; do
    task_key=${variant}_${scenario}
    nice -n 10 "$task_python" -m scripts.run_variant_stop_window_review \
      --comparison analysis/2026-10-22_variant_comparison/v1/full_$variant \
      --weather analysis/2026-10-22_variant_weather/v1/full_$variant \
      --stop analysis/2026-10-12_stop_windows/v2/outputs \
      --matching analysis/2026-10-23_stop_scenario_matching/v1/$task_key \
      --output analysis/2026-10-23_stop_scenario_review/v1/$task_key
    nice -n 10 "$task_python" outputs/2026-10-12/verify_stop_review.py \
      analysis/2026-10-23_stop_scenario_review/v1/$task_key
    nice -n 10 "$task_python" -m scripts.run_variant_paired_responses_v2 \
      --comparison analysis/2026-10-22_variant_comparison/v1/full_$variant \
      --matching analysis/2026-10-23_stop_scenario_matching/v1/$task_key \
      --measurement analysis/2026-10-23_variant_measurement/v1/full_$variant \
      --stop-review analysis/2026-10-23_stop_scenario_review/v1/$task_key \
      --design docs/superpowers/specs/2026-10-12-matching-design.md \
      --output analysis/2026-10-23_stop_scenario_responses/v1/$task_key
    nice -n 10 "$task_python" outputs/2026-10-12/verify_paired_responses.py \
      analysis/2026-10-23_stop_scenario_responses/v1/$task_key \
      > analysis/2026-10-23_stop_scenario_matching/v1/$task_key.responses.verify.json
    echo "Verified changed scenario responses $task_key"
  done
done
