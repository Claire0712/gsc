#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in absolute35 q95 min3 min6 season6 all_year absolute30; do
    task_output=analysis/2026-10-22_variant_comparison/v1/full_$variant
    test ! -e "$task_output"
    nice -n 10 "$task_python" -m scripts.run_comparison_windows \
      --preflight analysis/2026-10-20_variant_preflight/v1/$variant \
      --candidate analysis/2026-10-20_variant_candidate/v1/$variant \
      --connection analysis/2026-10-07_event_inputs/connection_10min \
      --quality analysis/2026-10-07_parallel_prep/ioda \
      --heat analysis/2026-10-20_variant_heat_stage/v1/$variant \
      --stop analysis/2026-10-12_stop_windows/v2/outputs \
      --cyclone analysis/2026-10-11_cyclone_screen/v4/full_outputs \
      --calendar-dir analysis/2026-10-21_variant_calendar/v1/full_$variant \
      --baseline analysis/2026-10-20_variant_baseline/v1/full_$variant \
      --output "$task_output"
    nice -n 10 "$task_python" outputs/2026-10-22_verify_variant_comparison.py \
      --verifier outputs/2026-10-12/verify_comparison_windows.py \
      --output "$task_output" \
      --baseline analysis/2026-10-20_variant_baseline/v1/full_$variant \
      --calendar analysis/2026-10-21_variant_calendar/v1/full_$variant \
      --heat analysis/2026-10-20_variant_heat_stage/v1/$variant \
      > "$task_output.verify.json"
    echo "Verified comparison $variant"
done
