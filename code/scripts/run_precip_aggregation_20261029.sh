#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PY=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
"$PY" -c 'import json;from pathlib import Path;p=Path("analysis/2026-10-29_precip_aggregation/v1/pilot_202201_v2.verify.json");d=json.loads(p.read_text());assert d["status"]=="verified" and d["rows"]==436'
test ! -e analysis/2026-10-29_precip_aggregation/v1/full_outputs
set --
for year in 2022 2023 2024 2025; do
 for month in 01 02 03 04 05 06 07 08 09 10 11 12; do set -- "$@" "$year$month"; done
done
set -- "$@" 202601
exec nice -n 10 "$PY" -m scripts.aggregate_archived_precip \
 --weights data/era5_land/population_weights/worldpop2025_adm0_era5land_weights.npz \
 --metadata data/era5_land/population_weights/weights_metadata.json \
 --weight-receipt analysis/2026-10-28_precip_weights/global_cell_comparison.json \
 --audit-manifest analysis/2026-10-12_precip_mask_full/v1/full_outputs/manifest.json \
 --raw data/weather_controls/raw_monthly \
 --output analysis/2026-10-29_precip_aggregation/v1/full_outputs --months "$@"
