'use strict';
const el = id => document.getElementById(id);
const number = (v, digits=2) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
const date = v => new Date(v * 1000).toLocaleString();
let paused = false, last = null, lastFetch = 0, failed = true, busy = false;
function freshness() {
  if (!last) return;
  const elapsed = (Date.now() - lastFetch) / 1000;
  const age = last.latest ? Math.max(0, last.server_time + elapsed - last.latest.received_at) : null;
  const stale = age !== null && age > last.stale_after_seconds;
  el('age').textContent = age === null ? 'Waiting for telemetry' : `${Math.floor(age)}s since last reception`;
  const h = last.health;
  el('connection').textContent = failed ? 'Gateway unavailable · displayed values may be old' : paused ? 'Display paused' : h.storage_error ? 'Storage error' : !h.subscription_ready ? 'MQTT receiver disconnected or subscription pending' : stale ? 'Telemetry stale' : last.latest ? 'Receiving telemetry' : 'Waiting for telemetry';
  el('connection').className = failed || h.storage_error || !h.subscription_ready ? 'error' : paused || stale || !last.latest ? '' : 'good';
  document.body.dataset.readingState = failed || stale || paused ? 'old' : 'current';
  el('sample-state').textContent = last.latest ? (failed || stale || paused ? 'Last stored reading' : 'Latest received reading') : 'No sample';
}
function chart(data) {
  const svg = el('chart'); svg.replaceChildren();
  const width = Math.max(280, svg.getBoundingClientRect().width);
  svg.setAttribute('viewBox', `0 0 ${width} 240`);
  const rows = data.history, end = data.server_time, start = end - Number(el('window').value) * 60;
  const values = rows.filter(r => r.sample.sensor_status === 'OK' && Number.isFinite(r.sample.do_mg_l)).map(r => r.sample.do_mg_l);
  const low = values.length ? Math.max(0, Math.min(...values)-0.5) : 0;
  const high = values.length ? Math.max(low+1, Math.max(...values)+0.5) : 10;
  const make = (tag, attrs) => {const n=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));svg.append(n);return n;};
  for(let i=0;i<4;i++) {const y=15+i*65;make('line',{x1:55,x2:width-15,y1:y,y2:y,stroke:'#34485b'});const t=make('text',{x:0,y:y+5,fill:'#b0c1ce','font-size':14});t.textContent=(high-i*(high-low)/3).toFixed(1);}
  let path='', previous=null;
  for (const row of rows) {
    const s=row.sample;
    if(s.sensor_status!=='OK'||!Number.isFinite(s.do_mg_l)){previous=null;continue;}
    const x=55+(row.received_at-start)/(end-start)*(width-70), y=15+(high-s.do_mg_l)/(high-low)*195;
    const join=previous && row.received_at-previous.received_at<=20 && s.boot_id===previous.sample.boot_id && s.sequence===previous.sample.sequence+1;
    path+=`${join?'L':'M'}${x.toFixed(2)},${y.toFixed(2)} `;
    const dot=make('circle',{cx:x,cy:y,r:2.5,fill:'#67d6ee'});
    const title=document.createElementNS(svg.namespaceURI,'title');title.textContent=`${date(row.received_at)}: ${number(s.do_mg_l)} mg/L`;dot.append(title);previous=row;
  }
  make('path',{d:path,fill:'none',stroke:'#67d6ee','stroke-width':2});
  el('empty').hidden=values.length>0;
  svg.setAttribute('aria-label',values.length?`Dissolved oxygen: ${values.length} valid readings. See recent readings table below.`:'No valid dissolved oxygen readings in this window');
  el('start').textContent=new Date(start*1000).toLocaleTimeString();el('end').textContent=new Date(end*1000).toLocaleTimeString();
}
function render(data) {
  const s=data.latest?.sample;
  for (const [id,key] of [['do','do_mg_l'],['temp','temperature_c'],['sat','saturation_pct']]) el(id).textContent=number(s?.[key]);
  el('received').textContent=data.latest?date(data.latest.received_at):'No samples yet';
  for (const [id,key] of [['sensor','sensor_status'],['clock','clock_status'],['calibration','calibration_status'],['compensation','compensation_status'],['sequence','sequence'],['missed','not_forwarded_before_sample'],['firmware','firmware_version']]) {el(id).textContent=s?.[key]??'—';el(id).dataset.state=s?.[key]??'UNKNOWN';}
  el('notice').textContent=!s?'Waiting for the first stored reading. No simulated data is displayed.':s.sensor_status!=='OK'?`Sensor reports ${s.sensor_status}. Invalid measurements remain missing.`:`${s.clock_status==='UNSYNCED'?'Node clock is unsynchronized. ':''}History uses gateway receive time, not sample time. Calibration: ${s.calibration_status}; compensation: ${s.compensation_status}.`;
  el('pipeline').textContent=data.health.storage_error?'SQLite write failed · recording needs attention':data.health.subscription_ready?'MQTT subscription active · readings committed to SQLite before acknowledgment':'MQTT subscription pending · showing stored history';
  chart(data);el('rows').replaceChildren();
  for(const r of data.history.slice(-20).reverse()){const tr=document.createElement('tr');for(const text of [date(r.received_at),number(r.sample.do_mg_l),number(r.sample.temperature_c),r.sample.sensor_status]){const td=document.createElement('td');td.textContent=text;tr.append(td);}el('rows').append(tr);}
  freshness();
}
async function refresh() {
  if(paused||busy||document.hidden)return;
  busy=true;
  try{const response=await fetch(`/api/node_01?minutes=${el('window').value}`,{signal:AbortSignal.timeout(5000)});if(!response.ok)throw new Error('Gateway unavailable');const data=await response.json();if(paused)return;last=data;lastFetch=Date.now();failed=false;render(data);}
  catch{failed=true;el('connection').textContent='Gateway unavailable · retrying';el('connection').className='error';freshness();}
  finally{busy=false;}
}
el('window').addEventListener('change',()=>{if(paused){paused=false;el('pause').textContent='Pause display';el('pause').setAttribute('aria-pressed','false');}refresh();});
el('pause').addEventListener('click',()=>{paused=!paused;el('pause').textContent=paused?'Resume display':'Pause display';el('pause').setAttribute('aria-pressed',String(paused));freshness();if(!paused)refresh();});
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
setInterval(refresh,5000);setInterval(freshness,1000);refresh();

let resizeFrame;
window.addEventListener('resize',()=>{cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>{if(last)chart(last);});});
