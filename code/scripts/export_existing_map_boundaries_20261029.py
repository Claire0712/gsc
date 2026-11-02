"""Display-only simplification of retained ADM0; never used for population/exposure calculations."""
from pathlib import Path
import hashlib,json,time
import geopandas as gpd
from shapely.geometry import mapping
root=Path('/volume1/homes/Judy/GSC2027/HeatSignal')
source=root/'data/boundaries/geoBoundariesCGAZ_ADM0.gpkg'
out=root/'analysis/2026-10-29_map_boundaries/v1';assert not out.exists()
start=time.monotonic();frame=gpd.read_file(source)
assert frame.crs.to_epsg()==4326 and len(frame)==218
assert frame.shapeGroup.notna().all() and frame.shapeGroup.is_unique
features=[];fallback=[]
for _,r in frame.iterrows():
 geometry=r.geometry;assert not geometry.is_empty and geometry.is_valid
 simplified=geometry.simplify(.08,preserve_topology=True)
 if simplified.is_empty or not simplified.is_valid:
  simplified=geometry;fallback.append(str(r.shapeGroup))
 features.append(dict(type='Feature',properties=dict(country_id=str(r.shapeGroup),name=str(r.shapeName)),geometry=mapping(simplified)))
out.mkdir(parents=True)
path=out/'adm0_display.geojson';path.write_text(json.dumps(dict(type='FeatureCollection',features=features),ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=dict(status='completed',source=str(source),source_sha256=sha(source),output_sha256=sha(path),countries=len(features),tolerance_degrees=.08,preserve_topology=True,fallback_original=fallback,elapsed_seconds=time.monotonic()-start,scope='Retained geoBoundaries ADM0 generalized for display only; exact existing shapeGroup IDs. Not outage footprints or revised scientific aggregation boundaries.')
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest))
