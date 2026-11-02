"""Normalize overlapping polygon parts in display-only retained outlines."""
import argparse,hashlib,json
from pathlib import Path
import shapely
from shapely.geometry import shape,mapping
from shapely.ops import unary_union

def normalize_outline(geom):
 if geom.is_valid:return geom
 if geom.geom_type!='MultiPolygon' or not all(p.is_valid for p in geom.geoms):raise ValueError('Unsupported invalid outline; do not silently repair coordinates')
 fixed=unary_union(tuple(geom.geoms))
 assert fixed.is_valid and fixed.geom_type in ('Polygon','MultiPolygon') and fixed.bounds==geom.bounds
 return fixed

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();assert not a.output.exists();x=json.loads(a.input.read_text());changes=[]
 for f in x['features']:
  old=shape(f['geometry']);new=normalize_outline(old)
  if not old.is_valid:
   changes.append(dict(country=f['properties']['shapeGroup'],name=f['properties']['shapeName'],before_area_deg2_not_valid_area=old.area,after_area_deg2=new.area,bounds_unchanged=new.bounds==old.bounds,rule='Geometric union of individually valid multipart land polygons; no new hole or smoothing'));f['geometry']=mapping(new);f['properties']['display_nested_shell_union']=True
 assert all(shape(f['geometry']).is_valid for f in x['features']);a.output.mkdir(parents=True);p=a.output/'adm1_orientation.geojson';p.write_text(json.dumps(x,ensure_ascii=False)+'\n');receipt=dict(input=str(a.input),input_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest(),output_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),shapely=shapely.__version__,geos=shapely.geos_version_string,features=len(x['features']),changes=changes,all_output_geometries_valid=True,scope='Display context only. Input preserved; no ERA5 values, population weights or network mapping changed.')
 (a.output/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
