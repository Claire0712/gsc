#!/usr/bin/env python3
"""Reproduce the ten independently verified TON/BGP scalar checks on Judy.

Run with the existing judy environment and -W error. This reads the immutable
v1 pilot and its original inputs; it does not rerun the baseline or edit files.
The verification body is the exact warning-free code executed for the receipt.
"""
import csv,gzip,hashlib,json,math,statistics,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
t0=time.monotonic()
r=Path("/volume1/homes/Judy/GSC2027/HeatSignal");base=r/"analysis/2026-10-12_connection_baseline/v1";out=base/"pilot_ton_bgp"
manifest=json.loads((out/"manifest.json").read_text())
for name,e in manifest["outputs"].items():
 b=(out/name).read_bytes();assert len(b)==e["bytes"] and hashlib.sha256(b).hexdigest()==e["sha256"]
annual={int(x["year"]):5*int(x["valid_points"])>=4*int(x["expected_points"]) for x in csv.DictReader((r/"analysis/2026-10-07_parallel_prep/ioda/coverage_annual.csv").read_text().splitlines()) if x["country_id"]=="TO" and x["signal"]=="bgp"}
groups={}
with gzip.open(r/"analysis/2026-10-07_event_inputs/heat_catalogue/daily_heat_flags.csv.gz","rt") as f:
 for x in csv.DictReader(f):
  if x["country_id"]=="TON" and x["analysis_event_id"]:
   groups.setdefault(x["analysis_event_id"],[]).append(int(datetime.fromisoformat(x["date"]).replace(tzinfo=timezone.utc).timestamp()))
heat=[(min(v),max(v)+4*86400) for v in groups.values()]
stop=[x["windows"]["main"] for x in json.loads((r/"analysis/2026-10-12_stop_windows/v2/outputs/stop_windows.json").read_text())["records"] if x["country_id"]=="TON" and x["windows"]]
cy=json.loads((r/"analysis/2026-10-11_cyclone_screen/v4/pilot_ton/TON.json").read_text())
windows={mode:[(x["start_utc_seconds"],x["end_utc_seconds"]) for x in cy["windows"] if x["radius_km"]==300 and x["half_width_hours"]==24 and x["mode"]==mode] for mode in ["conservative","known"]}
def bits(s):
 b=int(any(a<=s<z for a,z in heat))+2*int(any(a<=s<z for a,z in stop))
 c=any(a<=s<=z for a,z in windows["conservative"]);k=any(a<=s<=z for a,z in windows["known"])
 return b+4*int(c)+8*int(c and not k)+16*int(s<1514851200 or s>=1767139200)
cache={}
def obs(s):
 d=datetime.fromtimestamp(s,timezone.utc)
 if d.year<2022 or d.year>2025:return float("nan")
 q=str(d.year)+"Q"+str((d.month-1)//3+1)
 if q not in cache:
  with np.load(r/("analysis/2026-10-07_event_inputs/connection_10min/ioda_"+q+"_bgp.npz"),allow_pickle=False) as a:cache[q]=(a["interval_start_utc"].copy(),a["values"][list(a["country_ids"]).index("TO")].copy())
 ts,vs=cache[q];i=np.searchsorted(ts,s)
 return float(vs[i]) if i<len(ts) and ts[i]==s else float("nan")
files=sorted(out.glob("points_*.npz"));checks=[]
for fi,slot in [(i,0) for i in range(7)]+[(0,1),(0,-1),(4,100)]:
 with np.load(files[fi],allow_pickle=False) as a:
  t=int(a["target_timestamps"][slot]);refs=[];sides=[]
  for j,day in enumerate([-28,-21,-14,-7,7,14,21,28]):
   s=t+day*86400;v=obs(s);year=datetime.fromtimestamp(s,timezone.utc).year
   assert bits(s)==int(a["reference_exclusion_bits"][slot,j])
   assert annual.get(year,False)==bool(a["reference_annual_eligible"][slot,j])
   if math.isfinite(v) and v>=0 and annual.get(year,False) and bits(s)==0:refs.append(v);sides.append(day)
  m=statistics.median(refs) if refs else float("nan")
  expected=m if len(refs)>=4 and min(sides)<0<max(sides) and m>0 else float("nan")
  actual=float(a["baseline"][slot]);assert actual==expected or math.isnan(actual) and math.isnan(expected)
  assert len(refs)==int(a["reference_count"][slot])
  assert sum(d<0 for d in sides)==int(a["before_count"][slot])
  assert sum(d>0 for d in sides)==int(a["after_count"][slot])
  assert bits(t)==int(a["target_exclusion_bits"][slot])
  valid=math.isfinite(obs(t)) and obs(t)>=0 and annual.get(datetime.fromtimestamp(t,timezone.utc).year,False) and math.isfinite(expected)
  assert valid==bool(a["analysis_available"][slot])
  assert (valid and bits(t)&22==0)==bool(a["target_analysis_unconfounded"][slot])
  checks.append(dict(event=str(a["event_id"]),target_utc=datetime.fromtimestamp(t,timezone.utc).isoformat(),reference_count=len(refs),baseline=actual if math.isfinite(actual) else None))
for path in files:
 with np.load(path,allow_pickle=False) as a:
  n=len(a["target_timestamps"]);assert n and np.all(np.diff(a["target_timestamps"])==600)
  assert a["reference_exclusion_bits"].shape==(n,8) and a["reference_annual_eligible"].shape==(n,8)
  assert a["target_analysis_unconfounded"].shape==(n,) and a["target_exclusion_bits"].dtype==np.uint8
audit=list(csv.DictReader((out/"event_baseline_audit.csv").read_text().splitlines()))
hashes={str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((base/"scripts").glob("*.py"))}
print(json.dumps(dict(output_hashes_verified=len(manifest["outputs"]),npz_schema_verified=len(files),scalar_checks=checks,verification_elapsed_seconds=time.monotonic()-t0,full_unconfounded_events=sum(x["full_observed_unconfounded"]=="True" for x in audit),deployed_script_sha256=hashes),allow_nan=False))
