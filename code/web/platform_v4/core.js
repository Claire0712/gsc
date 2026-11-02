(function(root){
 'use strict';
 const api={
 filter:(rows,s,names)=>rows.filter(r=>r.signal===s.signal&&(s.year==='all'||r.year_month.startsWith(s.year))&&(!s.clean||r.full_observed_unconfounded)&&(!s.search||(r.country_id+' '+(names[r.country_id]?.name||'')).toLowerCase().includes(s.search.toLowerCase()))),
 at:(r,h)=>{const p=r.hourly_ratio.find(p=>p[0]===Number(h));return p&&Number.isFinite(p[1])?p[1]:null},
 value:(r,mode,h)=>mode==='heat'?r.exposure.hd_c_days:mode==='quality'?r.metrics.coverage_fraction:mode==='social'?(r.signal==='ping-slash24'&&Number.isFinite(r.social?.dlep_proxy)?r.social.dlep_proxy:null):api.at(r,h),
 project:(lon,lat)=>[(Number(lon)+180)/360*1000,(90-Number(lat))/180*500],
 outline:g=>{let rings=g.type==='Polygon'?g.coordinates:g.type==='MultiPolygon'?g.coordinates.flat():[];return rings.map(ring=>{let previous=null;return ring.map(p=>{let [x,y]=api.project(p[0],p[1]);if(!Number.isFinite(x)||!Number.isFinite(y))throw Error('Invalid boundary coordinate');let command=previous===null||Math.abs(x-previous)>500?'M':'L';previous=x;return command+x.toFixed(2)+','+y.toFixed(2)}).join(' ')}).join(' ')}
 };
 if(typeof module!=='undefined')module.exports=api;else root.HeatCore=api;
})(typeof globalThis!=='undefined'?globalThis:this);
