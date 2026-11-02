"""Retained geoBoundaries ADM1 outlines for orientation; no IODA mapping."""
import argparse,hashlib,json,sqlite3
from pathlib import Path
from shapely import wkb
from shapely.geometry import mapping
from .run_connection_baseline import Sources

def run(a):
 out=Path(a.output);assert not out.exists();p=Path('data/boundaries/geoBoundariesCGAZ_ADM1.gpkg');src=Sources();src.verify(p,dict(sha256='6467b0433a6db18e0653fcc30214b431c84df3a0d43a47e468def9e1bdc4d4d3',bytes=152539136));features=[]
 with sqlite3.connect('file:'+str(p.resolve())+'?mode=ro',uri=True) as db:
  srs=db.execute("select srs_id from gpkg_geometry_columns where table_name='globalADM1'").fetchone()[0];assert srs==4326
  for name,group,ident,blob in db.execute('select shapeName,shapeGroup,shapeID,geom from globalADM1 where shapeGroup in (?,?,?)',('USA','CHN','AUS')):
   assert blob[:2]==b'GP';envelope=(blob[3]>>1)&7;offset=8+8*{0:0,1:4,2:6,3:6,4:8}[envelope];geom=wkb.loads(blob[offset:]);assert not geom.is_empty
   simple=geom.simplify(.025,preserve_topology=True);features.append(dict(type='Feature',properties=dict(shapeName=name,shapeGroup=group,shapeID=ident,source_geometry_valid=bool(geom.is_valid)),geometry=mapping(simple)))
 src.verify(Path(__file__));src.check();out.mkdir(parents=True);(out/'adm1_orientation.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features),ensure_ascii=False)+'\n');summary=dict(source_sha256=src.entries,features=len(features),counts={c:sum(f['properties']['shapeGroup']==c for f in features) for c in ('USA','CHN','AUS')},invalid_source_geometries=sum(not f['properties']['source_geometry_valid'] for f in features),simplification_degrees=.025,scope='Display outlines from retained source only. Not approved IODA ADM1 links, native state population allocation, historical border inference or a state connectivity result.');(out/'manifest.json').write_text(json.dumps(dict(summary=summary,output_sha256=hashlib.sha256((out/'adm1_orientation.geojson').read_bytes()).hexdigest()),indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args())
