#!/bin/sh
# Sequential execution of already tested/verified baseline and audit commands.
# Any existing output halts; inspect it before resuming, never overwrite/restart.
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in q95 min3 min6 season6 all_year absolute30; do
    task_output=analysis/2026-10-20_variant_baseline/v1/full_$variant
    if test -e "$task_output"; then
        echo "Existing output requires inspection: $task_output" >&2
        exit 1
    fi
    nice -n 10 "$task_python" -m scripts.run_connection_baseline \
        --preflight analysis/2026-10-20_variant_preflight/v1/$variant \
        --candidate analysis/2026-10-20_variant_candidate/v1/$variant \
        --connection analysis/2026-10-07_event_inputs/connection_10min \
        --quality analysis/2026-10-07_parallel_prep/ioda \
        --heat analysis/2026-10-20_variant_heat_stage/v1/$variant \
        --stop analysis/2026-10-12_stop_windows/v2/outputs \
        --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs \
        --output "$task_output"
    nice -n 10 "$task_python" -m scripts.verify_variant_baseline_full \
        --project /volume1/homes/Judy/GSC2027/HeatSignal --output "$task_output" \
        --heat analysis/2026-10-20_variant_heat_stage/v1/$variant \
        --candidate analysis/2026-10-20_variant_candidate/v1/$variant \
        --preflight analysis/2026-10-20_variant_preflight/v1/$variant \
        > analysis/2026-10-20_variant_baseline/v1/full_$variant.verify.json
    echo "Verified baseline $variant"
done
