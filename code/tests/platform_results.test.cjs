const {test}=require('node:test'),assert=require('node:assert/strict');
const R=require('../web/platform_v4/results.js');
const fixture={primary:{curves:[{signal:'AP',groups:2,countries:2,days:[0],beta:[0],interval95:[[0,0]]}],conditional_recovery:[{signal:'bgp',sample:'primary',model:'M1',estimable:false,reason:'Insufficient recovery endpoints'}]},spatial:{countries:[{country_id:'A',country_nonexceedance_mean_pixel_fraction:0,country_exceedance_mean_pixel_fraction:1,total_days:2}]}};
test('fixed reference is distinct from estimated zero, selections preserve original records',()=>{
 const before=JSON.stringify(fixture),r=R.eventSeries(fixture,'ping-slash24');assert.equal(r.points[0].beta,0);assert.deepEqual(r.reference,{day:-1,beta:0,fixed:true});assert.equal(JSON.stringify(fixture),before);
 const bad=JSON.parse(before);bad.primary.curves[0].beta[0]=null;assert.throws(()=>R.eventSeries(bad,'ping-slash24'));
});
test('unestimable recovery and missing country never become zero effects',()=>{
 const r=R.recoverySeries(fixture,'bgp','M1');assert.equal(r.available,false);assert.equal(r.points.length,0);assert.equal(r.records[0].estimable,false);assert.equal(R.spatialRecord(fixture,'A').country_nonexceedance_mean_pixel_fraction,0);assert.equal(R.spatialRecord(fixture,'absent'),null);
});
