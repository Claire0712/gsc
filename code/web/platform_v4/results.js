(function(root){
'use strict';
const labels={'ping-slash24':'AP',bgp:'BGP','merit-nt':'Telescope'};
function eventSeries(payload,signal){
 const row=payload.primary.curves.find(r=>r.signal===labels[signal]);
 if(!row)return {available:false,points:[],reference:{day:-1,beta:0,fixed:true}};
 if(row.days.length!==row.beta.length||row.days.length!==row.interval95.length||row.days.includes(-1))throw Error('Invalid estimated-day/reference contract');
 const points=row.days.map((day,i)=>{const ci=row.interval95[i];if(!Number.isInteger(day)||!Number.isFinite(row.beta[i])||!Array.isArray(ci)||ci.length!==2||!ci.every(Number.isFinite)||ci[0]>ci[1])throw Error('Missing or invalid coefficient interval');return {day,beta:row.beta[i],interval:ci.slice()}});
 return {available:true,signal:row.signal,color:row.color||'#3C5488',groups:row.groups,countries:row.countries,points,reference:{day:-1,beta:0,fixed:true},records:row};
}
function recoverySeries(payload,signal,model){
 const records=payload.primary.conditional_recovery.filter(r=>r.signal===signal&&r.model===model),term=model==='M1'?'hd_c_days':'ntrd_c_days';
 const points=records.filter(r=>r.estimable).map(r=>{const i=r.terms.indexOf(term),ci=r.hazard_ratio95[i],value=r.hazard_ratio[i];if(i<0||!Number.isFinite(value)||value<=0||!Array.isArray(ci)||ci.length!==2||!ci.every(v=>Number.isFinite(v)&&v>0)||ci[0]>ci[1])throw Error('Invalid recovery interval');return {sample:r.sample,rows:r.rows,countries:r.countries,events:r.events,value,interval:ci.slice()}});
 return {available:points.length>0,term,points,records};
}
function spatialRecord(payload,country){return payload.spatial.countries.find(r=>r.country_id===country)||null}
const api={eventSeries,recoverySeries,spatialRecord};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.HeatResults=api;
})(typeof globalThis!=='undefined'?globalThis:this);
