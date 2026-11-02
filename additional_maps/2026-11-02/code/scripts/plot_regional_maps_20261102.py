"""Publication-scale native-grid regional maps, from frozen derived CSV only."""
from pathlib import Path
import argparse,hashlib,json,math,os,datetime
os.environ.setdefault("SOURCE_DATE_EPOCH",str(int(datetime.datetime(2026,11,2,tzinfo=datetime.timezone.utc).timestamp())))
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from shapely import contains_xy
from shapely.ops import transform as geometry_transform
from pyproj import CRS,Transformer
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import colors,font_manager,ticker
from matplotlib.patches import Patch
BOX={'USA':(-125,-66,24,50),'CHN':(74,135,18,54),'AUS':(112,154,-44,-10)}
PROJ={'USA':'EPSG:5070','CHN':'+proj=aea +lat_1=25 +lat_2=47 +lat_0=0 +lon_0=105 +datum=WGS84 +units=m +no_defs','AUS':'EPSG:3577'}
FIELDS=['absolute35_days_per_year','local_q90_days_per_year','local_hot_on_national_nonhot_percent']
LABELS=['Mean annual days\nUTC Tmax > 35 °C','Mean annual days\nUTC Tmax > local Q90','Local Q90 exceedance on national\nnon-exceedance days (%)']
TITLES=['Tmax > 35 °C','Local relative exceedance','Aggregation contrast']
CMAPS=[colors.LinearSegmentedColormap.from_list('absolute',['#fff7ec','#fdbb84','#e34a33','#7f0000']),colors.LinearSegmentedColormap.from_list('relative',['#fcfbfd','#bcbddc','#807dba','#3f007d']),colors.LinearSegmentedColormap.from_list('hidden',['#f7fbff','#9ecae1','#4292c6','#084594'])]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,required=True);ap.add_argument('--boundaries',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output;assert not out.exists();out.mkdir(parents=True)
 d=pd.read_csv(args.data);assert set(d.country_id)==set(BOX) and d.groupby('country_id').size().min()>1000 and not d.duplicated(['country_id','grid_index']).any();assert d[FIELDS].notna().all().all() and (d.valid_target_days==1461).all();g=gpd.read_file(args.boundaries);assert g.crs.to_epsg()==4326 and g.geometry.is_valid.all();font=font_manager.findfont('Arial',fallback_to_default=False)
 plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial'],'font.size':7.5,'axes.labelsize':7.5,'xtick.labelsize':7,'ytick.labelsize':7,'legend.fontsize':7,'axes.unicode_minus':False,'pdf.fonttype':42,'svg.fonttype':'none','svg.hashsalt':'HeatSignal-regional-20261102','axes.linewidth':.5,'savefig.bbox':None})
 maxima={f:float(math.ceil(d[f].max()/10)*10) for f in FIELDS};annual_fields=[f'local_q90_percent_{y}' for y in range(2022,2026)];annualmax=float(math.ceil(d.loc[d.country_id=='USA',annual_fields].to_numpy().max()/5)*5);saved=[];captions={};scales={};regions={}
 def prepare(cid,extent):
  extent=tuple(extent);west,east,south,north=extent;shape=g.loc[g.shapeGroup==cid].copy();shape.geometry=shape.geometry.intersection(box(west,south,east,north));shape=shape.loc[~shape.geometry.is_empty];tf=Transformer.from_crs(4326,PROJ[cid],always_xy=True)
  xs=np.r_[np.linspace(west,east,40),np.linspace(west,east,40),np.full(40,west),np.full(40,east)];ys=np.r_[np.full(40,south),np.full(40,north),np.linspace(south,north,40),np.linspace(south,north,40)];px,py=tf.transform(xs,ys);bounds=(min(px),max(px),min(py),max(py));return shape.to_crs(PROJ[cid]),tf,bounds
 def draw(ax,cid,frame,field,vmax,cmap,extent,state=None):
  state_context,tf,bounds=prepare(cid,extent);state_context.plot(ax=ax,color='#e7e7e7',edgecolor='none',zorder=1)
  lo=np.arange(frame.longitude.min()-.125,frame.longitude.max()+.126,.25);la=np.arange(frame.latitude.max()+.125,frame.latitude.min()-.126,-.25);a=np.full((len(la)-1,len(lo)-1),np.nan);ri=np.rint((frame.latitude.max()-frame.latitude)/.25).astype(int);ci=np.rint((frame.longitude-frame.longitude.min())/.25).astype(int);vals=frame[field].to_numpy().copy()
  if state is not None:vals[~contains_xy(state,frame.longitude.to_numpy(),frame.latitude.to_numpy())]=np.nan
  a[ri,ci]=vals;xx,yy=tf.transform(*np.meshgrid(lo,la));mesh=ax.pcolormesh(xx,yy,np.ma.masked_invalid(a),cmap=cmap,vmin=0,vmax=vmax,shading='flat',rasterized=False,zorder=2)
  state_context.boundary.plot(ax=ax,color='#757575',linewidth=.25,zorder=4)
  west,east,south,north=extent
  step=10 if east-west>25 else 2
  for long in np.arange(math.ceil(west/step)*step,east,step):
   x,y=tf.transform(np.full(60,long),np.linspace(south,north,60));ax.plot(x,y,color='#666666',lw=.2,ls=(0,(1,3)),alpha=.45,zorder=3)
  for lat in np.arange(math.ceil(south/step)*step,north,step):
   x,y=tf.transform(np.linspace(west,east,60),np.full(60,lat));ax.plot(x,y,color='#666666',lw=.2,ls=(0,(1,3)),alpha=.45,zorder=3)
  lon=west+(.90 if state is None else .08)*(east-west);lat=south+.12*(north-south);x0,y0=tf.transform(lon,lat);x1,y1=tf.transform(lon,lat+.14*(north-south));ax.annotate('',xy=(x1,y1),xytext=(x0,y0),arrowprops=dict(arrowstyle='-|>',lw=.6,color='#333333'),zorder=6);ax.text(x1,y1+(bounds[3]-bounds[2])*.018,'N',fontsize=7,ha='center',va='bottom',zorder=6)
  dx=(bounds[1]-bounds[0])*.015;dy=(bounds[3]-bounds[2])*.015;ax.set_xlim(bounds[0]-dx,bounds[1]+dx);ax.set_ylim(bounds[2]-dy,bounds[3]+dy);ax.set_aspect('equal');ax.set_axis_off();return mesh
 def export(fig,name,caption):
  fig.canvas.draw()
  for legend in fig.legends:
   for axis in fig.axes:
    label=axis.xaxis.label
    if label.get_visible() and label.get_text():assert not legend.get_window_extent().overlaps(label.get_window_extent()),'Legend overlaps colourbar label'
  from matplotlib.text import Text
  texts=[t for t in fig.findobj(Text) if t.get_visible() and t.get_text()];assert min(t.get_fontsize() for t in texts)>=7
  for ext in ('png','pdf','svg'):fig.savefig(out/(name+'.'+ext),dpi=300,bbox_inches=None,facecolor='white')
  saved.append(name);captions[name]=caption;plt.close(fig)
 for cid in BOX:
  f=d.loc[d.country_id==cid];height={'USA':70,'CHN':80,'AUS':92}[cid];fig=plt.figure(figsize=(180/25.4,height/25.4),dpi=300)
  for j,field in enumerate(FIELDS):
   ax=fig.add_axes([.025+.33*j,.30,.30,.60]);mesh=draw(ax,cid,f,field,maxima[field],CMAPS[j],BOX[cid]);fig.text(.025+.33*j,.93,chr(97+j),fontsize=9,fontweight='bold',va='bottom');fig.text(.047+.33*j,.93,TITLES[j],fontsize=8,va='bottom')
   cax=fig.add_axes([.055+.33*j,.26,.24,.025]);bar=fig.colorbar(mesh,cax=cax,orientation='horizontal',ticks=[0,mesh.norm.vmax/2,mesh.norm.vmax]);bar.ax.tick_params(width=.4,length=2,pad=2);bar.set_label(LABELS[j],fontsize=7,labelpad=3);bar.outline.set_linewidth(.4);bar.solids.set_rasterized(False)
  fig.legend(handles=[Patch(facecolor='#e7e7e7',label='No assigned population support')],loc='lower center',bbox_to_anchor=(.5,.005),frameon=False,handlelength=1)
  weight=float(f.country_population_weight.sum());regions[cid]=dict(cells=len(f),represented_country_weight=weight,national_nonhot_days=int(f.national_nonhot_days.iloc[0]));export(fig,cid+'_regional_metrics',f'{cid}, 2022–2025, discrete ERA5 0.25° cells with positive original fixed-2025 country population weight. Left: mean annual days strictly above 35°C; middle: mean annual days above each cell’s own 2018–2021 circular-calendar Q90; right: local Q90 exceedance frequency conditional on the archived whole-country index not exceeding its country Q90. {len(f)} supported cells, {weight:.8%} of original country weight represented; conditional denominator {int(f.national_nonhot_days.iloc[0])} days. Grey is unsupported/unpopulated for this map, not zero heat. Boundaries are orientation only. USA covers the contiguous country view; its conditioning index still uses the original whole-country weights, including excluded areas. No subnational connectivity effect or equipment hazard threshold is inferred. All three country figures share each metric’s untruncated linear colour domain.');scales[cid]=maxima
 # All four USA years retained, same local threshold reference and common percentage scale.
 usa=d.loc[d.country_id=='USA'];fig=plt.figure(figsize=(180/25.4,130/25.4),dpi=300)
 for i,year in enumerate(range(2022,2026)):
  row,col=divmod(i,2);ax=fig.add_axes([.025+.50*col,.55-.42*row,.46,.37]);mesh=draw(ax,'USA',usa,f'local_q90_percent_{year}',annualmax,CMAPS[1],BOX['USA']);fig.text(.025+.50*col,.94-.42*row,chr(97+i),fontsize=9,fontweight='bold',va='bottom');fig.text(.048+.50*col,.94-.42*row,str(year),fontsize=8,va='bottom')
 cax=fig.add_axes([.24,.075,.52,.018]);bar=fig.colorbar(mesh,cax=cax,orientation='horizontal',ticks=[0,mesh.norm.vmax/2,mesh.norm.vmax]);bar.set_label('Days above each cell’s local Q90 (%)',fontsize=7.5,labelpad=3);bar.ax.tick_params(length=2,width=.4);bar.outline.set_linewidth(.4);bar.solids.set_rasterized(False)
 export(fig,'USA_annual_relative_exceedance','Contiguous USA, all four study years, native 0.25° populated cells. Each panel uses the same local 2018–2021 Q90 reference; percentage denominators are the complete UTC days in that calendar year (366 in 2024). Shared colour scale; no data clipping or interpolation. This is a retrospective year comparison, not a four-year trend estimate, a physiological heat-risk scale or a network-fault map. Grey denotes no original assigned population support.')
 # Geographic display examples chosen before regional summaries, not ranked by effect.
 state_names=['California','Texas','New York'];fig=plt.figure(figsize=(180/25.4,88/25.4),dpi=300);state_summaries=[]
 for i,name in enumerate(state_names):
  sub=g.loc[(g.shapeGroup=='USA')&(g.shapeName==name)];assert len(sub)==1;geom=sub.geometry.iloc[0];west,south,east,north=geom.bounds;extent=(west-.35,east+.35,south-.35,north+.35);f=usa.loc[usa.longitude.between(extent[0],extent[1])&usa.latitude.between(extent[2],extent[3])];ax=fig.add_axes([.025+.33*i,.27,.30,.63]);mesh=draw(ax,'USA',f,FIELDS[0],maxima[FIELDS[0]],CMAPS[0],extent,state=geom);fig.text(.025+.33*i,.94,chr(97+i),fontsize=9,fontweight='bold',va='bottom');fig.text(.047+.33*i,.94,name,fontsize=8,va='bottom');inside=contains_xy(geom,f.longitude.to_numpy(),f.latitude.to_numpy());values=f.loc[inside,FIELDS[0]];state_summaries.append(dict(state=name,cell_centres_inside=len(values),minimum=float(values.min()),median=float(values.median()),maximum=float(values.max())))
 cax=fig.add_axes([.26,.14,.48,.025]);bar=fig.colorbar(mesh,cax=cax,orientation='horizontal',ticks=[0,mesh.norm.vmax/2,mesh.norm.vmax]);bar.set_label('Mean annual days with UTC Tmax > 35°C',fontsize=7.5,labelpad=3);bar.ax.tick_params(length=2,width=.4);bar.outline.set_linewidth(.4);bar.solids.set_rasterized(False)
 export(fig,'USA_state_detail_absolute_heat','California, Texas and New York display enlargements of the same USA 0.25° cell data, 2022–2025. Only cells whose centres fall inside the retained simplified state polygon are coloured; border-cell assignment is approximate. All panels share the USA/China/Australia absolute-threshold colour domain. No new fine-resolution temperature, state-native population allocation, state network observation, state resilience ranking or causal effect is created by zooming. Grey means no displayed supported cell; source-resolution remains roughly tens of kilometres. State examples were selected for geographic contrast before summaries, not by significance.')
 (out/'captions.json').write_text(json.dumps(captions,ensure_ascii=False,indent=2)+'\n');(out/'state_display_ranges.json').write_text(json.dumps(state_summaries,indent=2)+'\n');profile=dict(regions=regions,shared_domains={f:[0,maxima[f]] for f in FIELDS},usa_annual_percentage_domain=[0,annualmax],figures=saved,panels=16,reference='2018–2021 local Q90; ±15d; >=112 valid/all4years; target leap-day interpolation',font=font,placed_width_mm=180,minimum_font_pt=7,scope='Descriptive spatial weather diagnostics, no new network or causal result.')
 (out/'profile_and_design.json').write_text(json.dumps(profile,indent=2)+'\n');receipt=dict(inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.data,args.boundaries,Path(__file__))},outputs={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in out.iterdir()},status='rendered_native_review_pending',raster_dpi=300,editable_vectors=True);(out/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(profile,indent=2))
if __name__=='__main__':main()
