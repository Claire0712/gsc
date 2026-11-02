#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in q95 min3 min6 season6 all_year absolute30; do
  nice -n 10 "$task_python" -m scripts.run_variant_recovery_qualification \
    --panel analysis/2026-10-22_variant_panel/v1/full_$variant \
    --metrics analysis/2026-10-21_variant_metrics/v1/$variant \
    --baseline analysis/2026-10-20_variant_baseline/v1/full_$variant \
    --output analysis/2026-10-22_variant_recovery_qualification/v1/full_$variant
  nice -n 10 "$task_python" outputs/2026-10-15_verify_recovery_qualification.py \
    analysis/2026-10-22_variant_recovery_qualification/v1/full_$variant \
    > analysis/2026-10-22_variant_recovery_qualification/v1/full_$variant.verify.json
  nice -n 10 "$task_python" -m scripts.run_recovery_cox \
    --qualified analysis/2026-10-22_variant_recovery_qualification/v1/full_$variant \
    --output analysis/2026-10-22_variant_recovery_cox/v1/full_$variant
  nice -n 10 "$task_python" outputs/2026-10-15_verify_recovery_cox.py \
    analysis/2026-10-22_variant_recovery_cox/v1/full_$variant \
    > analysis/2026-10-22_variant_recovery_cox/v1/full_$variant.verify.json
  echo "Verified recovery $variant"
done
