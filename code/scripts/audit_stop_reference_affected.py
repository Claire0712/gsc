"""Locate actual forward reference queries changed by hypothetical STOP masks."""
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

root = Path('/volume1/homes/Judy/GSC2027/HeatSignal')
records = json.loads((root/'analysis/2026-10-12_stop_windows/v2/outputs/stop_windows.json').read_text())['records']
route = list(csv.DictReader((root/'analysis/2026-10-08_candidate_gate/outputs/forward_candidates.csv').open()))
def stamp(text):
    return int(datetime.fromisoformat(text.replace('Z','+00:00')).replace(tzinfo=timezone.utc).timestamp())
for scenario in ('unknown_end_plusminus7','unknown_end_plusminus30'):
    counts = Counter()
    for event in route:
        windows = [r['windows'] for r in records if r['country_id']==event['country_id'] and r['windows']]
        if not windows:
            continue
        for day in (-28,-21,-14,-7,7,14,21,28):
            start=stamp(event['start_date'])+day*86400
            end=stamp(event['end_exclusive_utc'])+72*3600+day*86400
            # Count exact 600-second UTC reference labels in the union difference.
            for t in range(start,end,600):
                extra=any(w[scenario][0]<=t<w[scenario][1] for w in windows)
                primary=any(w['main'][0]<=t<w['main'][1] for w in windows)
                counts[event['country_id']]+=int(extra and not primary)
    print(json.dumps(dict(scenario=scenario,additional_reference_queries=sum(counts.values()),countries=[(k,v) for k,v in counts.most_common() if v])))
