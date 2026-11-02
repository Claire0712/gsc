const {test}=require('node:test'),assert=require('node:assert/strict');
const c=require('../web/platform_v3/core.js');
test('social layer preserves observed zero, excludes other signals and missing',()=>{
 const r={signal:'ping-slash24',social:{dlep_proxy:0},hourly_ratio:[[0,1.2]]};
 assert.equal(c.value(r,'social',0),0);
 assert.equal(c.value({...r,social:{dlep_proxy:null}},'social',0),null);
 assert.equal(c.value({...r,signal:'bgp'},'social',0),null);
 assert.equal(c.value({...r,social:null},'social',0),null);
 assert.equal(c.value(r,'response',0),1.2);
});
