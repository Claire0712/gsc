(function(){
'use strict';
const payload=JSON.parse($('analysis-results').textContent),R=HeatResults;
const view=$('resultsView'),signal=$('resultsSignal'),model=$('resultsModel'),countrySelect=$('resultsCountry'),chart=$('resultsChart');
view.value=view.value||'event_study';signal.value=signal.value||'ping-slash24';model.value=model.value||'M1';
for(const r of [...payload.spatial.countries].sort((a,b)=>a.country_id.localeCompare(b.country_id))){const option=document.createElement('option');option.value=r.country_id;option.textContent=name(r.country_id)+' · '+r.country_id;countrySelect.append(option)}
countrySelect.value=payload.spatial.countries.some(r=>r.country_id==='USA')?'USA':payload.spatial.countries[0]?.country_id||'';
let current=null;
const text=(value,x,y,anchor='middle')=>{const e=svg('text',{x,y,'text-anchor':anchor,'font-size':12,fill:'#526a74'},chart);e.textContent=value;return e};
function line(x1,y1,x2,y2,attrs={}){return svg('line',{x1,y1,x2,y2,stroke:'#c5d2d6',...attrs},chart)}
function dotTitle(parent,value){svg('title',{},parent).textContent=value}
function evidence(){$('resultsEvidence').textContent=JSON.stringify({selection:current,scope:payload.scope,source_sha256:payload.source_sha256},null,2);}
function render(){
 chart.replaceChildren();$('resultsSignalLabel').hidden=view.value==='spatial';$('resultsModelLabel').hidden=view.value!=='recovery';$('resultsCountryLabel').hidden=view.value!=='spatial';
 $('resultsScope').textContent='固定研究样本：2022–2025。这里切换已核结果；上方的事件国家、年份与质量筛选不重估这些模型。';
 if(view.value==='event_study'){
  const r=R.eventSeries(payload,signal.value);current={view:view.value,signal:signal.value,records:r.records||null};
  if(!r.available){$('resultsSummary').textContent='该信号没有可用主曲线估计。';evidence();return}
  $('resultsSummary').textContent=r.signal+' · '+r.groups+' 个匹配事件 / '+r.countries+' 个国家；点为估计，竖线为边际95%国家WCU区间。-1日灰方块是固定参照，未连接各日。观察关联，主曲线未加降水调整。';
  const all=[0,...r.points.flatMap(p=>[p.beta,...p.interval])].map(v=>v*100),low=Math.min(...all),high=Math.max(...all),pad=(high-low||1)*.10,lo=low-pad,hi=high+pad,x=d=>80+(d+7)/14*770,y=v=>225-(v-lo)/(hi-lo)*190;
  for(let i=0;i<=4;i++){const value=lo+(hi-lo)*i/4;line(80,y(value),850,y(value));text(fmt(value,Math.abs(hi-lo)<1?3:1),70,y(value)+4,'end')}
  line(80,y(0),850,y(0),{'stroke-dasharray':'5 4',stroke:'#667b83'});line(x(0),30,x(0),225,{'stroke-dasharray':'3 3'});
  for(const p of r.points){line(x(p.day),y(p.interval[0]*100),x(p.day),y(p.interval[1]*100),{stroke:r.color,'stroke-width':2});const point=svg('circle',{cx:x(p.day),cy:y(p.beta*100),r:4,fill:r.color,tabindex:0,'data-result-point':'event'},chart);dotTitle(point,'日 '+p.day+'；估计 '+fmt(p.beta*100,4)+' pp；95%区间 ['+p.interval.map(v=>fmt(v*100,4)).join(', ')+'] pp')}
  const ref=svg('rect',{x:x(-1)-4,y:y(0)-4,width:8,height:8,fill:'#666666','data-fixed-reference':'true'},chart);dotTitle(ref,'固定参照日 -1：0；无估计区间');
  for(const day of [-7,-1,0,7])text(day,x(day),247);text('相对热过程开始日',465,273);text('连接比值差（百分点 pp）',80,18,'start');
 }else if(view.value==='recovery'){
  const r=R.recoverySeries(payload,signal.value,model.value);current={view:view.value,signal:signal.value,model:model.value,records:r.records};
  if(!r.available){$('resultsSummary').textContent='该信号没有足够的合格恢复端点，无法估计恢复HR；没有用零值代替。';evidence();return}
  $('resultsSummary').textContent=(signal.value==='ping-slash24'?'AP':'Telescope')+' · '+model.value+' / '+(model.value==='M1'?'HD':'NTRD')+'；受损风险集中的条件恢复，国家sandwich边际95%区间。完整72小时样本以未来观测完整为条件；AP稀疏估计属探索，数值一致不代表PH或独立删失通过，不作因果证明。';
  const limits=[1,...r.points.flatMap(p=>p.interval)],low=Math.min(...limits)*.92,high=Math.max(...limits)*1.08,x=v=>300+(Math.log(v)-Math.log(low))/(Math.log(high)-Math.log(low))*550;
  line(x(1),25,x(1),215,{'stroke-dasharray':'5 4',stroke:'#667b83'});
  r.points.forEach((p,i)=>{const y=80+i*90,color=signal.value==='ping-slash24'?'#3C5488':'#E64B35';text((p.sample==='primary'?'主风险集':'完整72小时观察')+' · '+p.rows+'条 / '+p.events+'恢复',285,y+4,'end');line(x(p.interval[0]),y,x(p.interval[1]),y,{stroke:color,'stroke-width':2});const marker=svg(p.sample==='primary'?'circle':'rect',p.sample==='primary'?{cx:x(p.value),cy:y,r:5,fill:color,'data-result-point':'recovery'}:{x:x(p.value)-5,y:y-5,width:10,height:10,fill:color,'data-result-point':'recovery'},chart);dotTitle(marker,'HR '+fmt(p.value,4)+'；95%区间 ['+p.interval.map(v=>fmt(v,4)).join(', ')+']；'+p.countries+'个国家')});
  for(const value of [.25,.5,.75,1,1.25,1.5,2,3,4])if(value>=low&&value<=high)text(String(value),x(value),243);text('条件恢复HR（log坐标；每1 °C·天）',575,273);
 }else{
  const r=R.spatialRecord(payload,countrySelect.value);current={view:'spatial',country_id:countrySelect.value,records:r};
  if(!r){$('resultsSummary').textContent='该实体缺少支持的空间汇总。';evidence();return}
  $('resultsSummary').textContent=name(r.country_id)+' · '+r.total_days+' 个有效国日；全国未超阈日的本地超阈人口比例均值 '+fmt(r.country_nonexceedance_mean_pixel_fraction*100,2)+'%，全国超阈日 '+fmt(r.country_exceedance_mean_pixel_fraction*100,2)+'%。固定2025人口权重；像元及全国Q90均以2018–2021日序±15天为参考。描述均值，不是事件损害或因果效应。';
  const rows=[['全国Tmax ≤ Q90',r.country_nonexceedance_mean_pixel_fraction,r.country_nonexceedance_days,'#3C5488'],['全国Tmax > Q90',r.country_exceedance_mean_pixel_fraction,r.country_exceedance_days,'#E64B35']];
  rows.forEach(([label,value,days,color],i)=>{const y=60+i*85;text(label+' · '+days+'日',270,y+24,'end');if(!Number.isFinite(value)){text('数据不足',300,y+24,'start');return}const bar=svg('rect',{x:285,y,width:Math.min(1,Math.max(0,value))*565,height:35,fill:color,'data-result-point':'spatial'},chart);dotTitle(bar,fmt(value*100,4)+'%')});
  for(const value of [0,.25,.5,.75,1])text(fmt(value*100,0)+'%',285+value*565,245);text('本像元Q90以上的人口权重比例 · 国家日均值',565,273);
 }
 evidence();
}
for(const control of [view,signal,model,countrySelect])control.onchange=render;
$('resultsDownload').onclick=()=>download(JSON.stringify({...current,scope:payload.scope,source_sha256:payload.source_sha256},null,2),'heatsignal-fixed-sample-results.json','application/json');
const w=payload.weather_definition;$('resultsWeather').textContent='国家统一太阳日天气定义：'+w.solar_events+' 个事件 / '+w.solar_weather_candidates+' 个天气候选；UTC '+w.utc_events+' / '+w.utc_weather_candidates+'。天气审计不等于太阳日网络效应认证。';
render();
})();
