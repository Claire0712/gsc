const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('actual archived dataset drives selection, layers, empty states and downloads',()=>{
 const html=fs.readFileSync(process.env.HEATSIGNAL_PLATFORM_HTML||'deliverables/2026-10-29_platform/index.html','utf8');
 class Element{constructor(){this.children=[];this.value='';this.textContent='';this.dataset={};this.classList={toggle(){}}}replaceChildren(...a){this.children=a}append(a){this.children.push(a)}setAttribute(k,v){this[k]=v}click(){if(this.onclick)this.onclick()}}
 const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
 for(const id of ['dataset','locations'])get(id).textContent=html.match(new RegExp('<script id="'+id+'" type="application/json">(.*?)</script>','s'))[1];
 const boundary=html.match(/<script id="boundaries" type="application\/json">(.*?)<\/script>/s);if(boundary)get('boundaries').textContent=boundary[1];
 get('year').value='all';get('signal').value='ping-slash24';get('clean').checked=false;
 const buttons=['heat','response','quality'].map(mode=>{let e=new Element();e.dataset.mode=mode;return e});let downloaded=false;
 const document={getElementById:get,createElement:()=>new Element(),createElementNS:()=>new Element(),querySelectorAll:()=>buttons};
 const context=vm.createContext({document,console,Blob,URL:{createObjectURL(){downloaded=true;return 'blob:test'},revokeObjectURL(){}},setTimeout:()=>{},setInterval:()=>1,clearInterval(){}});
 vm.runInContext(fs.readFileSync('web/platform/core.js','utf8'),context);vm.runInContext(fs.readFileSync('web/platform/app.js','utf8'),context);
 assert.equal(get('eventcount').textContent,910);assert.equal(get('countrycount').textContent,151);assert.equal(get('events').children.length,910);
 if(boundary)assert.equal(get('map').children.filter(e=>e.d&&e.fill==='none').length,218);
 let circles=get('map').children.filter(e=>e.role==='button');assert.equal(circles.length,151);circles[0].onclick();assert.ok(get('events').children.length<910);
 get('signal').value='bgp';get('signal').onchange();assert.equal(vm.runInContext('selected.signal',context),'bgp');
 buttons[1].onclick();assert.equal(vm.runInContext('mode',context),'response');
 get('time').value=1;get('time').oninput();assert.equal(vm.runInContext('hour',context),1);
 get('json').onclick();assert.equal(downloaded,true);
 get('search').value='no-such-country';get('search').oninput();assert.equal(get('eventcount').textContent,0);assert.equal(get('play').disabled,true);assert.equal(get('trace').children.length,0);
 get('reset').onclick();assert.equal(get('eventcount').textContent,910);assert.equal(get('play').disabled,false);
});
