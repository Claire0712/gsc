const {test}=require('node:test');const assert=require('node:assert/strict');
const c=require('../web/platform_v4/core.js');
test('filters preserve missing and country membership',()=>{
 const rows=[{country_id:'A',signal:'bgp',year_month:'2022-01',event_id:'a',full_observed_unconfounded:false,exposure:{hd_c_days:3}},{country_id:'B',signal:'bgp',year_month:'2023-01',event_id:'b',full_observed_unconfounded:true,exposure:{hd_c_days:9}}];
 assert.equal(c.filter(rows,{year:'2022',signal:'bgp',clean:false,search:''},{}).length,1);
 assert.equal(c.filter(rows,{year:'all',signal:'bgp',clean:true,search:''},{} )[0].event_id,'b');
});
test('zero is an observation and missing is never interpolated',()=>{
 const r={hourly_ratio:[[0,0],[1,null],[2,1.1]],metrics:{coverage_fraction:0,dhrd_hours:null},exposure:{hd_c_days:0}};
 assert.equal(c.at(r,0),0);assert.equal(c.at(r,1),null);assert.equal(c.at(r,3),null);
 assert.equal(c.value(r,'heat',0),0);assert.equal(c.value(r,'response',1),null);
 assert.equal(c.value(r,'quality',1),0);
});
test('map longitude wraps and latitude projects without invented geometry',()=>{
 assert.deepEqual(c.project(0,0),[500,250]);assert.deepEqual(c.project(180,90),[1000,0]);
});
test('boundary outlines break at antimeridian rather than spanning the map',()=>{
 const g={type:'Polygon',coordinates:[[[170,0],[-170,0],[-160,10]]]};
 const path=c.outline(g);assert.equal((path.match(/M/g)||[]).length,2);assert.equal((path.match(/L/g)||[]).length,1);
});
