"""Bounded WGS84 distance classification against native lon/lat polygons."""
import math
import numpy as np
from pyproj import Geod
from shapely import STRtree, prepare
from shapely.geometry import Point, box
try:
    from .cyclone_screen_core import candidate_boxes
except ImportError:
    from cyclone_screen_core import candidate_boxes


class BoundaryIndex:
    def __init__(self, geometry):
        if geometry.geom_type not in ('Polygon','MultiPolygon') or geometry.is_empty or not geometry.is_valid:
            raise ValueError('Valid nonempty polygon required')
        self.geometry = geometry
        prepare(geometry)
        self.geod = Geod(ellps='WGS84')
        self.chunks = []
        self.roundoff_coordinates = 0
        boxes = []
        polys = list(geometry.geoms) if geometry.geom_type=='MultiPolygon' else [geometry]
        for poly in polys:
            for ring in [poly.exterior, *poly.interiors]:
                xy = np.asarray(ring.coords)[:,:2].copy()
                if not np.isfinite(xy).all() or np.any(np.abs(xy[:,0])>180+1e-10) or np.any(np.abs(xy[:,1])>90+1e-10) or np.any(np.abs(np.diff(xy[:,0]))>180):
                    raise ValueError('Invalid coordinates or unsplit dateline ring')
                self.roundoff_coordinates += int(np.count_nonzero((np.abs(xy[:,0])>180)|(np.abs(xy[:,1])>90)))
                # Numerical endpoint roundoff only; never modify the source geometry.
                xy[:,0]=np.clip(xy[:,0],-180,180)
                xy[:,1]=np.clip(xy[:,1],-90,90)
                for start in range(0,len(xy)-1,256):
                    part=xy[start:min(start+257,len(xy))].copy()
                    self.chunks.append(part)
                    boxes.append(box(part[:,0].min(),part[:,1].min(),part[:,0].max(),part[:,1].max()))
        self.tree = STRtree(boxes)

    def classify(self, lon, lat):
        """100/300/500km hit flags; None means unresolved within 1m bounds."""
        query_boxes=candidate_boxes(lon,lat,500001)
        lon=(lon+180)%360-180
        thresholds=np.array([100000.,300000.,500000.])
        if self.geometry.covers(Point(lon,lat)) or (lon==-180 and self.geometry.covers(Point(180,lat))):
            return dict(within=[True]*3,lower_m=0.,upper_m=0.,iterations=0)
        selected=set()
        for bounds in query_boxes:
            selected.update(map(int,self.tree.query(box(*bounds))))
        aa=[];bb=[]
        for key in sorted(selected):
            part=self.chunks[key]; a,b=part[:-1],part[1:]
            lo,hi=np.minimum(a,b),np.maximum(a,b)
            keep=np.zeros(len(a),dtype=bool)
            for west,south,east,north in query_boxes:
                keep |= (lo[:,0]<=east)&(hi[:,0]>=west)&(lo[:,1]<=north)&(hi[:,1]>=south)
            aa.append(a[keep]);bb.append(b[keep])
        if not aa or not sum(map(len,aa)):
            return dict(within=[False]*3,lower_m=500001.,upper_m=None,iterations=0)
        a,b=np.concatenate(aa),np.concatenate(bb)
        # Unselected boundary portions lie outside the conservative 500001m cap.
        floor=500001.; upper=math.inf
        for iteration in range(61):
            def distance(points):
                return self.geod.inv(np.full(len(points),lon),np.full(len(points),lat),points[:,0],points[:,1])[2]
            da,db=distance(a),distance(b)
            length=6400000.*np.deg2rad(np.linalg.norm(b-a,axis=1))
            lower=np.maximum(0,(da+db-length)/2)
            upper=min(upper,float(np.minimum(da,db).min()))
            global_lower=min(floor,float(lower.min()))
            flags=[True if upper<=r else False if global_lower>r else None for r in thresholds]
            if None not in flags or upper-global_lower<=1 or iteration==60:
                return dict(within=flags,lower_m=global_lower,upper_m=upper,iterations=iteration)
            keep=lower<=min(upper,500001.)
            if (~keep).any(): floor=min(floor,float(lower[~keep].min()))
            if not keep.any():
                return dict(within=flags,lower_m=global_lower,upper_m=upper,iterations=iteration)
            a,b=a[keep],b[keep]; midpoint=(a+b)/2
            a,b=np.concatenate([a,midpoint]),np.concatenate([midpoint,b])
