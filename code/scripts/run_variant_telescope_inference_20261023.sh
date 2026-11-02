#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in absolute35 q95 min3 min6 season6 all_year absolute30; do
  if [ "$variant" = absolute35 ]; then task_responses=analysis/2026-10-23_variant_responses/v1/full_$variant; else task_responses=analysis/2026-10-23_variant_responses/v2/full_$variant; fi
    nice -n 10 "$task_python" -m scripts.run_variant_hour_curve \
      --daily analysis/2026-10-23_variant_daily_curve/v1/${variant}_merit-nt \
      --responses "$task_responses" \
      --output analysis/2026-10-23_variant_hour_curve/v1/${variant}_merit-nt
  nice -n 10 "$task_python" -m scripts.run_curve_inference \
    --estimates analysis/2026-10-23_variant_hour_curve/v1/${variant}_merit-nt \
    --output analysis/2026-10-23_variant_curve_inference/v1/${variant}_merit-nt
  nice -n 10 "$task_python" outputs/2026-10-12/verify_curve_inference.py \
    analysis/2026-10-23_variant_curve_inference/v1/${variant}_merit-nt \
    > analysis/2026-10-23_variant_hour_curve/v1/${variant}_merit-nt.inference.verify.json
  nice -n 10 "$task_python" -m scripts.run_wild_coefficients \
    --inference analysis/2026-10-23_variant_curve_inference/v1/${variant}_merit-nt \
    --output analysis/2026-10-23_variant_wild/v1/${variant}_merit-nt
  nice -n 10 "$task_python" outputs/2026-10-12/verify_wild_coefficients.py \
    analysis/2026-10-23_variant_wild/v1/${variant}_merit-nt \
    > analysis/2026-10-23_variant_hour_curve/v1/${variant}_merit-nt.wild.verify.json
  echo "Verified Telescope inference $variant"
done


