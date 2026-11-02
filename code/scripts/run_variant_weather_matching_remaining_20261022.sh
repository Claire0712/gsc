#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in q95 min3 min6 season6; do
  test -s analysis/2026-10-22_variant_comparison/v1/full_$variant.verify.json
  nice -n 10 "$task_python" -m scripts.run_variant_pre_weather \
    --comparison analysis/2026-10-22_variant_comparison/v1/full_$variant \
    --heat analysis/2026-10-20_variant_heat_stage/v1/$variant \
    --weather analysis/2026-10-06_era5_existing_data/country_daily \
    --batch analysis/2026-10-20_event_variants/v1/full_outputs/manifest.json \
    --source-heat analysis/2026-10-07_event_inputs/heat_catalogue/manifest.json \
    --output analysis/2026-10-22_variant_weather/v1/full_$variant
  nice -n 10 "$task_python" outputs/2026-10-12/verify_pre_weather.py \
    analysis/2026-10-22_variant_weather/v1/full_$variant \
    > analysis/2026-10-22_variant_weather/v1/full_$variant.verify.json
  nice -n 10 "$task_python" -m scripts.run_variant_matching \
    --comparison analysis/2026-10-22_variant_comparison/v1/full_$variant \
    --weather analysis/2026-10-22_variant_weather/v1/full_$variant \
    --design docs/superpowers/specs/2026-10-12-matching-design.md \
    --output analysis/2026-10-22_variant_matching/v1/full_$variant
  nice -n 10 "$task_python" outputs/2026-10-12/verify_matching.py \
    analysis/2026-10-22_variant_matching/v1/full_$variant \
    > analysis/2026-10-22_variant_weather/v1/full_$variant.matching.verify.json
  echo "Verified weather and matching $variant"
done

