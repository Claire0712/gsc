#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in absolute35 q95 min3 min6 season6 all_year absolute30; do
  nice -n 10 "$task_python" -m scripts.run_measurement_review \
    --comparison analysis/2026-10-22_variant_comparison/v1/full_$variant \
    --sync analysis/2026-10-11_synchronous_screen/v3/full_outputs \
    --evidence outputs/2026-10-11 \
    --output analysis/2026-10-23_variant_measurement/v1/full_$variant
  nice -n 10 "$task_python" outputs/2026-10-12/verify_measurement_review.py \
    analysis/2026-10-23_variant_measurement/v1/full_$variant \
    > analysis/2026-10-23_variant_measurement/v1/full_$variant.verify.json
  if [ "$variant" != absolute35 ]; then
    nice -n 10 "$task_python" -m scripts.run_variant_stop_window_review \
      --comparison analysis/2026-10-22_variant_comparison/v1/full_$variant \
      --weather analysis/2026-10-22_variant_weather/v1/full_$variant \
      --stop analysis/2026-10-12_stop_windows/v2/outputs \
      --matching analysis/2026-10-22_variant_matching/v1/full_$variant \
      --output analysis/2026-10-23_variant_stop_review/v1/full_$variant
    nice -n 10 "$task_python" outputs/2026-10-12/verify_stop_review.py \
      analysis/2026-10-23_variant_stop_review/v1/full_$variant \
      > analysis/2026-10-23_variant_measurement/v1/full_$variant.stop.verify.json
  fi
  echo "Verified reviews $variant"
done
