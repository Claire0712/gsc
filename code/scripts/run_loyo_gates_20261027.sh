#!/bin/sh
# Compose unchanged eligibility stages and independent audits; no new estimator.
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
test -s analysis/2026-10-27_loyo_catalogues/v1/full.interval.verify.json
for variant in omit_2018 omit_2019 omit_2020 omit_2021; do
 task_batch=analysis/2026-10-27_loyo_catalogues/v1/full_outputs
 task_heat=analysis/2026-10-27_loyo_heat_stage/v1/$variant
 task_preflight=analysis/2026-10-27_loyo_preflight/v1/$variant
 task_candidate=analysis/2026-10-27_loyo_candidate/v1/$variant
 task_annual=analysis/2026-10-27_loyo_annual/v1/$variant
 test ! -e "$task_heat"
 test ! -e "$task_preflight"
 test ! -e "$task_candidate"
 test ! -e "$task_annual"
 "$task_python" -m scripts.variant_heat_stage --batch "$task_batch" --variant "$variant" --output "$task_heat"
 "$task_python" -m scripts.prepare_analysis_preflight \
  --crosswalk data/metadata/ioda_worldbank_crosswalk.csv \
  --countries analysis/2026-10-06_era5_existing_data/weights/country_metadata.csv \
  --events "$task_heat/analysis_events.csv" \
  --stop analysis/2026-10-07_parallel_prep/auxiliary/stop_cleaned.csv --output-dir "$task_preflight"
 "$task_python" outputs/2026-10-20_verify_variant_preflight.py \
  --root analysis/2026-10-27_loyo_preflight/v1 --variant "$variant"
 nice -n10 "$task_python" -m scripts.audit_candidate_connectivity \
  --preflight-dir "$task_preflight" --connection-dir analysis/2026-10-07_event_inputs/connection_10min \
  --output-dir "$task_candidate"
 "$task_python" outputs/2026-10-20_verify_variant_candidate.py --root "$task_candidate" \
  --preflight "$task_preflight" --connection analysis/2026-10-07_event_inputs/connection_10min
 nice -n10 "$task_python" -m scripts.screen_event_annual_coverage \
  --quality-dir analysis/2026-10-07_parallel_prep/ioda --candidate-dir "$task_candidate" --output-dir "$task_annual"
 "$task_python" outputs/2026-10-20_verify_variant_annual.py \
  --root analysis/2026-10-27_loyo_annual/v1 --quality analysis/2026-10-07_parallel_prep/ioda
 echo "Verified LOYO eligibility $variant"
done
