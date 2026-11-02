const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('fixed-sample results controls preserve event data, unavailable recovery and spatial zero',()=>{
 const path=process.env.HEATSIGNAL_PLATFORM_HTML||'deliverables/2026-10-31_platform_v3c/index.html',html=fs.readFileSync(path,'utf8');
 const primary=JSON.parse(fs.readFileSync('deliverables/2026-11-01_primary_figures_v2/source_data.json','utf8'));
 const lines=fs.readFileSync('outputs/2026-10-31_pixel_country_summary.csv','utf8').trim().split('\n'),headers=lines.shift().split(',');
 const countries=lines.map(line=>Object.fromEntries(line.split(',').map((v,i)=>[headers[i],i===0?v:v===''?null:Number(v)])));
 const fixture={primary,spatial:{countries,summary:{}},weather_definition:JSON.parse(fs.readFileSync('deliverables/2026-11-01_COUNTRY_SOLAR_DEFINITION_COMPARISON.json','utf8')),source_sha256:{}};
 class Element{constructor(){this.children=[];this.value='';this.textContent='';this.dataset={};this.classList={toggle(){}}}replaceChildren(...a){this.children=a}append(a){this.children.push(a)}setAttribute(k,v){this[k]=v}click(){if(this.onclick)this.onclick()}}
 const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
 for(const id of ['dataset','locations','social','boundaries'])get(id).textContent=html.match(new RegExp('<script id="'+id+'" type="application/json">(.*?)</script>','s'))[1];
 const embedded=html.match(/<script id="analysis-results" type="application\/json">(.*?)<\/script>/s);get('analysis-results').textContent=embedded?embedded[1]:JSON.stringify(fixture);
 get('year').value='all';get('signal').value='ping-slash24';get('clean').checked=false;
 const buttons=['heat','response','quality','social'].map(mode=>{const e=new Element();e.dataset.mode=mode;return e}),blobs=[];
 const document={getElementById:get,createElement:()=>new Element(),createElementNS:()=>new Element(),querySelectorAll:()=>buttons};
 const context=vm.createContext({document,console,Blob:class{constructor(parts){this.parts=parts;blobs.push(this)}},URL:{createObjectURL(){return 'blob:test'},revokeObjectURL(){}},setTimeout:()=>{},setInterval:()=>1,clearInterval(){}});
 for(const file of ['core.js','app.js','results.js','results_app.js'])vm.runInContext(fs.readFileSync('web/platform_v4/'+file,'utf8'),context);
 assert.equal(get('eventcount').textContent,910);assert.equal(get('resultsChart').children.filter(e=>e['data-result-point']==='event').length,14);assert.equal(get('resultsChart').children.filter(e=>e['data-fixed-reference']==='true').length,1);assert.ok(get('resultsSummary').textContent.includes('202'));
 get('year').value='2022';get('year').onchange();assert.ok(get('eventcount').textContent<910);assert.ok(get('resultsSummary').textContent.includes('202'));assert.equal(get('resultsChart').children.filter(e=>e['data-result-point']==='event').length,14);
 get('resultsView').value='recovery';get('resultsSignal').value='bgp';get('resultsView').onchange();assert.equal(get('resultsChart').children.length,0);assert.ok(get('resultsSummary').textContent.includes('恢复端点'));assert.equal(JSON.parse(get('resultsEvidence').textContent).selection.signal,'bgp');
 get('resultsSignal').value='merit-nt';get('resultsModel').value='M2';get('resultsModel').onchange();assert.equal(get('resultsChart').children.filter(e=>e['data-result-point']==='recovery').length,2);assert.ok(get('resultsSummary').textContent.includes('PH'));
 get('resultsView').value='spatial';get('resultsCountry').value=countries.find(r=>r.country_nonexceedance_mean_pixel_fraction===0).country_id;get('resultsView').onchange();assert.ok(get('resultsSummary').textContent.includes('0.00%'));assert.ok(get('resultsSummary').textContent.includes('2018–2021'));assert.equal(get('resultsChart').children.filter(e=>e['data-result-point']==='spatial').length,2);
 get('resultsDownload').onclick();const downloaded=JSON.parse(blobs.at(-1).parts.join(''));assert.equal(downloaded.view,'spatial');assert.equal(downloaded.records.country_nonexceedance_mean_pixel_fraction,0);
 get('json').onclick();assert.ok(JSON.parse(blobs.at(-1).parts.join('')).event_id);assert.equal(get('eventcount').textContent<910,true);
});
