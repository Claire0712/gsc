'use strict';
const $=id=>document.getElementById(id),C=HeatCore;
const socialMap=JSON.parse($('social').textContent);
const data=JSON.parse($('dataset').textContent).map(r=>({...r,social:r.signal==='ping-slash24'?(socialMap[r.event_id]||null):null})),locations=JSON.parse($('locations').textContent);
const boundaries=JSON.parse($('boundaries').textContent||'{"features":[]}');
let mode='heat',country=null,selected=null,hour=0,timer=null,filtered=[];
const date=v=>new Date(v*1000).toISOString().slice(0,10);
const fmt=(v,d=2)=>Number.isFinite(v)?v.toFixed(d):'数据不足';
const name=id=>locations[id]?.name||id;
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ns='http://www.w3.org/2000/svg';
function svg(tag,attrs,parent){let el=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,v));parent.append(el);return el}
function pause(){clearInterval(timer);timer=null;$('play').textContent='▶ 播放'}
function update(){
 pause();filtered=C.filter(data,{year:$('year').value,signal:$('signal').value,clean:$('clean').checked,search:$('search').value},locations);
 if(country&&!filtered.some(r=>r.country_id===country))country=null;
 let candidates=filtered.filter(r=>!country||r.country_id===country).sort((a,b)=>b.metrics.event_start-a.metrics.event_start||a.event_id.localeCompare(b.event_id));
 selected=candidates.find(r=>r.event_id===selected?.event_id)||candidates[0]||null;hour=0;
 $('countrycount').textContent=new Set(filtered.map(r=>r.country_id)).size;$('eventcount').textContent=filtered.length;
 renderList(candidates);renderMap();renderEvent();
}
function renderList(rows){
 $('events').replaceChildren();$('listcount').textContent=rows.length+' 个';
 if(!rows.length){$('events').textContent='没有符合筛选条件的事件';return}
 // Render all matching events, not an undocumented first-page truncation.
 for(const r of rows){let b=document.createElement('button');b.className='event'+(r.event_id===selected?.event_id?' selected':'');b.setAttribute('aria-pressed',String(r.event_id===selected?.event_id));
 let title=document.createElement('strong');title.textContent=name(r.country_id)+' · '+r.country_id;
 let sub=document.createElement('small');sub.textContent=date(r.metrics.event_start)+' · '+r.exposure.span_days+'天 · HD '+fmt(r.exposure.hd_c_days);
 b.append(title,sub);b.onclick=()=>{pause();selected=r;hour=0;renderList(rows);renderEvent();renderMap()};$('events').append(b)}
}
function chooseCountry(id){country=id;update()}
function color(v,max){if(!Number.isFinite(v))return '#b7c2c8';let t=mode==='response'?Math.max(0,Math.min(1,(1-v)/.4)):mode==='quality'?1-Math.max(0,Math.min(1,v)):mode==='social'?Math.log1p(Math.max(0,v))/Math.log1p(max||1):Math.max(0,Math.min(1,v/(max||1)));return `rgb(${Math.round(36+187*t)},${Math.round(153-40*t)},${Math.round(139-71*t)})`}
function renderMap(){
 const map=$('map');map.replaceChildren();
 for(let lon=-180;lon<=180;lon+=30){let [x]=C.project(lon,0);svg('line',{x1:x,y1:0,x2:x,y2:500,stroke:'#dce7ea','stroke-width':.7},map);if(lon>-180&&lon<180)svg('text',{x:x+4,y:488,fill:'#91a2aa','font-size':10},map).textContent=lon+'°'}
 for(let lat=-60;lat<=60;lat+=30){let [,y]=C.project(0,lat);svg('line',{x1:0,y1:y,x2:1000,y2:y,stroke:'#dce7ea','stroke-width':.7},map);svg('text',{x:6,y:y-5,fill:'#91a2aa','font-size':10},map).textContent=lat+'°'}
 for(const feature of boundaries.features){let p=svg('path',{d:C.outline(feature.geometry),fill:'none',stroke:'#9eb2b9','stroke-width':.65,'pointer-events':'none'},map);svg('title',{},p).textContent=feature.properties.name}
 const representatives=new Map();for(const r of filtered){let old=representatives.get(r.country_id);if(!old||r.metrics.event_start>old.metrics.event_start)representatives.set(r.country_id,r)}
 if(selected)representatives.set(selected.country_id,selected);
 const max=Math.max(1,...[...representatives.values()].map(r=>mode==='social'?C.value(r,'social',hour):r.exposure.hd_c_days).filter(Number.isFinite));let absent=0;
 for(const [id,r] of representatives){let loc=locations[id];if(!loc||!Number.isFinite(loc.lon)||!Number.isFinite(loc.lat)){absent++;continue}
 let [x,y]=C.project(loc.lon,loc.lat),v=C.value(r,mode,hour),point=svg('circle',{cx:x,cy:y,r:id===selected?.country_id?8:5.5,fill:color(v,max),tabindex:0,role:'button','aria-label':name(id)+' '+date(r.metrics.event_start),class:id===selected?.country_id?'selected':''},map);
 svg('title',{},point).textContent=name(id)+' · '+date(r.metrics.event_start)+' · '+(mode==='heat'?'HD '+fmt(v):mode==='quality'?'有效覆盖 '+fmt(v*100,1)+'%':mode==='social'?'DLEP 加权代理 '+fmt(v,0):'连接/参照 '+fmt(v));
 const hover=()=>{$('tooltip').textContent=name(id)+' · '+date(r.metrics.event_start)+' · '+(Number.isFinite(v)?fmt(v):'当前层数据不足')};point.onmouseenter=hover;point.onfocus=hover;
 point.onclick=()=>chooseCountry(id);point.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseCountry(id)}};
 }
 $('low').textContent=mode==='heat'?'HD 0 °C·天':mode==='quality'?'完整支持':mode==='social'?'DLEP 0 · log1p 色标':'连接/参照 ≥ 1';$('high').textContent=mode==='heat'?fmt(max)+' °C·天':mode==='quality'?'覆盖不足':mode==='social'?([...representatives.values()].some(r=>Number.isFinite(C.value(r,'social',hour)))?fmt(Math.max(0,...[...representatives.values()].map(r=>C.value(r,'social',hour)).filter(Number.isFinite)),0)+' · 加权代理':'无可用社会权重'):'连接缺口';
 $('mapscope').textContent='每国显示筛选范围内最近一次事件；所选国家使用当前事件。'+(mode==='response'?'连接层按各事件起点后的相同第 '+hour+' 小时比较，不是同一日全球快照。':mode==='social'?'社会层仅支持 AP：DHRD × 固定2025人口 × 可用互联网比例。其他信号为不适用；灰点保留缺失。整窗代理不随小时变化，不是断网人数、人时或国家排名。':'高温与质量为整窗摘要，不随播放伪造变化。')+(absent?' '+absent+'个国家缺少可验证定位，仅保留在事件列表。':'');
}
function renderEvent(){
 if(!selected){$('title').textContent='没有符合条件的事件';$('subtitle').textContent='请调整筛选条件';$('metrics').replaceChildren();$('facts').replaceChildren();$('trace').replaceChildren();$('time').disabled=true;for(const id of ['json','csv','play','evidenceToggle'])$(id).disabled=true;return}
 for(const id of ['time','json','csv','play','evidenceToggle'])$(id).disabled=false;
 const r=selected,m=r.metrics,e=r.exposure;
 $('title').textContent=name(r.country_id)+' / '+date(m.event_start);$('subtitle').textContent=r.country_id+' · '+r.event_id;
 $('state').textContent=r.full_observed_unconfounded?'完整且无已标记混杂':'需查看质量限制';
 const vals=[['DHRD',fmt(m.dhrd_hours),'小时 · 非真实断网时长'],['核心保持率',Number.isFinite(m.maintenance_core)?fmt(m.maintenance_core*100,1)+'%':'数据不足','连接达到参照95%的槽比例'],['窗口有效覆盖',fmt(m.coverage_fraction*100,1)+'%','缺失不填零'],['核心平均缺口',Number.isFinite(m.mean_deficit_core)?fmt(m.mean_deficit_core*100,2)+'%':'数据不足','归一化技术信号']];
 $('metrics').innerHTML=vals.map(([a,b,c])=>`<div class="metric"><span>${escape(a)}</span><strong>${escape(b)}</strong><small>${escape(c)}</small></div>`).join('');
 const recovery=m.recovery||{},facts=[['事件跨度',e.span_days+'天 / '+e.hot_days+'个热日'],['最高日 Tmax',fmt(e.absolute_tmax_c)+' °C'],['累计热剂量 HD',fmt(e.hd_c_days)+' °C·天'],['稳定恢复状态',recovery.status==='confirmed'?fmt(recovery.confirmation_hours)+'小时后确认':recovery.status==='not_applicable'?'不适用：不属于主恢复风险集':recovery.status||'不可计算'],['技术状态原标签',m.state],['三信号口径',r.signal==='ping-slash24'?'主动可达性':r.signal==='bgp'?'路由可见性':'非请求背景流量']];
 const social=r.social;
 facts.push(['DLEP 社会加权代理',r.signal!=='ping-slash24'?'不适用：仅 AP 支持':fmt(social?.dlep_proxy,0)+' · 非断网人数/人时'],['人口与互联网权重',social?'固定2025人口 '+fmt(social.population_2025,0)+'；互联网 '+(Number.isFinite(social.internet?.value)?fmt(social.internet.value*100,2):'数据不足')+'% / '+(social.internet?.source_year??'来源缺失')+'年；指标发布日期未知':'当前信号无社会权重']);
 $('facts').innerHTML=facts.map(([a,b])=>`<div><span class="muted">${escape(a)}</span><b>${escape(b)}</b></div>`).join('');
 $('evidence').textContent=JSON.stringify({event_id:r.event_id,country_id:r.country_id,signal:r.signal,source_point_file:r.source_point_file,qualification_reasons:r.qualification_reasons,full_observed_unconfounded:r.full_observed_unconfounded,final_sample_eligible:r.final_sample_eligible,upstream_audit:r.upstream_audit,recovery,social_weighting:social,social_scope:'AP整窗DHRD×固定2025人口×可用互联网比例；非实际人数/人时；未证明指标历史实时可用'},null,2);
 $('time').max=Math.max(0,...r.hourly_ratio.map(p=>p[0]));$('time').value=hour;renderTrace();
}
function renderTrace(){
 if(!selected)return;let m=selected.metrics,points=selected.hourly_ratio,total=Number($('time').max)||1,end=(m.event_end_exclusive-m.event_start)/3600;
 let max=Math.max(1.1,...points.filter(p=>Number.isFinite(p[1])).map(p=>p[1]))*1.05,x=h=>50+h/total*825,y=v=>195-v/max*165;
 const chart=$('trace');chart.replaceChildren();svg('rect',{x:x(end),y:15,width:Math.max(0,x(total)-x(end)),height:180,fill:'#edf3f4'},chart);
 for(const v of [0,.5,1]){svg('text',{x:40,y:y(v)+4,'font-size':11,fill:'#687d85','text-anchor':'end'},chart).textContent=String(v);svg('line',{x1:50,y1:y(v),x2:875,y2:y(v),stroke:'#dbe5e7','stroke-dasharray':v===1?'5 4':'0'},chart)}
 let path='',open=false;for(const [h,v]of points){if(!Number.isFinite(v)){open=false;continue}path+=(open?'L':'M')+x(h).toFixed(2)+','+y(v).toFixed(2)+' ';open=true}
 svg('path',{d:path,fill:'none',stroke:'#007f79','stroke-width':2},chart);svg('line',{x1:x(hour),x2:x(hour),y1:15,y2:195,stroke:'#df7444','stroke-width':1.5},chart);
 let v=C.at(selected,hour);if(v!==null)svg('circle',{cx:x(hour),cy:y(v),r:4,fill:'#df7444'},chart);
 for(const h of [...new Set([0,end,total])])svg('text',{x:x(h),y:220,'text-anchor':'middle','font-size':11,fill:'#687d85'},chart).textContent=h+' h';
 $('clock').textContent=hour+' h · '+(v===null?'缺测':fmt(v,3));
}
function download(content,filename,type){let url=URL.createObjectURL(new Blob([content],{type})),a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
for(const id of ['year','signal','clean'])$(id).onchange=update;$('search').oninput=update;
$('world').onclick=()=>{country=null;update()};$('reset').onclick=()=>{country=null;$('search').value='';$('year').value='all';$('clean').checked=false;update()};
for(const b of document.querySelectorAll('[data-mode]'))b.onclick=()=>{mode=b.dataset.mode;document.querySelectorAll('[data-mode]').forEach(n=>n.classList.toggle('active',n===b));renderMap()};
$('time').oninput=()=>{hour=Number($('time').value);renderTrace();if(mode==='response')renderMap()};
$('play').onclick=()=>{if(timer){pause();return}if(hour>=Number($('time').max))hour=0;$('play').textContent='Ⅱ 暂停';timer=setInterval(()=>{hour++;$('time').value=hour;renderTrace();if(mode==='response')renderMap();if(hour>=Number($('time').max))pause()},140)};
$('json').onclick=()=>{if(selected)download(JSON.stringify(selected,null,2),selected.event_id+'_'+selected.signal+'.json','application/json')};
$('csv').onclick=()=>{if(selected)download('hours_since_event_start,connection_to_reference_ratio\n'+selected.hourly_ratio.map(([h,v])=>h+','+(v===null?'':v)).join('\n'),selected.event_id+'_'+selected.signal+'.csv','text/csv')};
$('evidenceToggle').onclick=()=>{$('evidenceDetails').open=!$('evidenceDetails').open};update();
