#!/bin/sh
set -eu
cd /volume1/homes/Judy/GSC2027/HeatSignal
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
task_python=/volume1/homes/Judy/miniconda3/envs/judy/bin/python
for signal in ping-slash24 bgp merit-nt; do
 for setting in A B; do
  for model in M1 M2; do
   # Original AP A/M1 complete and independently checked: do not duplicate it.
   if [ "$signal/$setting/$model" = ping-slash24/A/M1 ]; then continue; fi
   task_key=${signal}_${setting}_${model}
   task_output=analysis/2026-10-24_country_sensitivity/v1/full_$task_key
   test ! -e "$task_output"
   nice -n 10 "$task_python" -m scripts.run_country_sensitivity \
    --panel analysis/2026-10-13_event_panel/v1/full_outputs --signal "$signal" --setting "$setting" --model "$model" --output "$task_output"
   nice -n 10 "$task_python" outputs/2026-10-24_verify_country_sensitivity.py "$task_output" > "$task_output.verify.json"
   echo "Verified country sensitivity $task_key"
  done
 done
done
