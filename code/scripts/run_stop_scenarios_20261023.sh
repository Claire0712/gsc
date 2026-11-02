#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for variant in q95 min3 min6 season6 all_year absolute30 absolute35; do
  for scenario in unknown_end_plusminus7 unknown_end_plusminus30; do
    task_output=analysis/2026-10-23_stop_scenario_matching/v1/${variant}_${scenario}
    if [ "${variant}_${scenario}" != q95_unknown_end_plusminus7 ]; then
      nice -n 10 "$task_python" -m scripts.run_stop_scenario_matching \
        --comparison analysis/2026-10-22_variant_comparison/v1/full_$variant \
        --weather analysis/2026-10-22_variant_weather/v1/full_$variant \
        --stop-review analysis/2026-10-23_variant_stop_review/v1/full_$variant \
        --scenario "$scenario" --design docs/superpowers/specs/2026-10-12-matching-design.md \
        --output "$task_output"
    fi
    nice -n 10 "$task_python" outputs/2026-10-23_verify_stop_scenario_matching.py \
      "$task_output" > "$task_output.verify.json"
    echo "Verified target scenario $variant $scenario"
  done
done
