'use strict';
const el = id => document.getElementById(id);
const number = (v, digits=2) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
const date = v => new Date(v * 1000).toLocaleString();
let paused = false, pausedAt = 0, last = null, lastFetch = 0, failed = true, busy = false;

const snapshots = {}, fetchTimes = {}, fetchErrors = {};
let predictionData = null, predictionFetchTime = 0, predictionFailed = false;
const nodeFor = m => m.node.toLowerCase().replace(' ', '_');
const addresses = {
  router: '192.168.88.1', gateway: '192.168.88.250',
  'Node 01': '192.168.88.101', 'Node 02': '192.168.88.102',
  'Node 03': '192.168.88.103', 'Node 04': '192.168.88.104',
  'Node 05': '192.168.88.105', 'Camera 06': '192.168.88.106',
  'Node 07': '192.168.88.107'
};
const accuracy = {
  do: {delta:0.6, note:'±0.6 mg/L; ±3% of 20 mg/L full scale'},
  orp: {delta:5, note:'±5 mV; specified at 25°C in 222 mV standard'},
  temperature: {delta:0.5, note:'±0.5°C; specified at 25°C'},
  temperature_orp: {delta:0.5, note:'±0.5°C'}
};
const measurements = [
  {id:'temperature', name:'Temperature', group:'Physical properties', node:'Node 01', probe:'DO probe', key:'temperature_c', unit:'°C', live:true},
  {id:'temperature_orp', name:'Temperature (ORP probe)', group:'Physical properties', node:'Node 02', probe:'ORP probe', key:'temperature_c', unit:'°C', live:true},
  {id:'turbidity', name:'Turbidity', group:'Physical properties', node:'Node 04', description:'No turbidity readings are available. This sensor is planned for a later commissioning step.'},
  {id:'conductivity', name:'Electrical conductivity', group:'Physical properties', node:'Node 05', description:'No conductivity readings are available. Sensor model and wiring are still to be confirmed.'},
  {id:'do', name:'Dissolved oxygen', group:'Chemical properties', node:'Node 01', key:'do_mg_l', unit:'mg/L', live:true},
  {id:'orp', name:'Oxidation–reduction potential', group:'Chemical properties', node:'Node 02', key:'orp_mv', unit:'mV', live:true},
  {id:'ph', name:'pH', group:'Chemical properties', node:'Node 03', description:'No pH readings are available. The sensor has not been integrated with this dashboard.'},
  {id:'uv254', name:'UV254 / optical COD proxy', group:'Chemical properties', node:'Node 07', description:'Hardware has not been selected. Any optical COD estimate will require site-specific validation and is not a laboratory BOD result.'},
  {id:'camera', name:'RGB camera', group:'Image information', node:'Camera 06', description:'No camera is connected. Images, capture times and visual observations will appear after camera integration.'}
];
const temperatureMeasurements = measurements.filter(m => m.live && m.key === 'temperature_c');
const detailHref = m => m.id === 'temperature' ? '#temperature_do' : `#${m.id}`;
let activeMeasurement = measurements.find(m => m.id === 'do');
function setupNavigation() {
  const nav = el('sensor-nav');
  nav.innerHTML = '<a href="#overview" class="nav-overview">Overview</a><a href="#predictions" class="nav-overview">Prediction dashboard</a><a href="#network" class="nav-overview">IP &amp; MAC</a>';
  for (const group of ['Chemical properties','Physical properties','Image information']) {
    const heading = document.createElement('h2'); heading.textContent=group; nav.append(heading);
    const section=document.createElement('section'); section.className='measurement-group';
    const title=document.createElement('h3'); title.textContent=group; section.append(title);
    for (const m of measurements.filter(m=>m.group===group)) {
      const link=document.createElement('a'); link.href=`#${m.id}`; link.textContent=m.name;
      if(m.key!=='temperature_c' || m===temperatureMeasurements[0]) nav.append(link);
      const row=document.createElement('a'); row.href=detailHref(m); row.className='measurement-row';
      const label=document.createElement('span'); label.className='measurement-name'; label.textContent=m.id==='temperature'?'Temperature (DO probe)':m.name;
      const value=document.createElement('strong'); value.id=`value-${m.id}`; if(!m.live)value.className='not-integrated'; value.textContent=m.live?'—':'Not integrated';
      const state=document.createElement('span'); state.id=`state-${m.id}`; state.className='measurement-state'; state.textContent=m.live?'Waiting for data':''; state.hidden=!m.live;
      row.append(label,value,state); section.append(row);
    }
    el('overview-groups').append(section);
  }
}
function setupNetwork() {
  const devices = [
    {key:'router', name:'Router', role:'MikroTik / WebFig'},
    {key:'gateway', name:'Jetson Orin Nano', role:'Gateway / Ethernet', mac:'AC:3A:E2:AB:F6:AC'},
    {key:'Node 01', role:'DO / Temperature', mac:'64:E8:33:75:BB:4C'},
    {key:'Node 02', role:'ORP / Temperature', mac:'30:30:F9:3B:81:B4'},
    {key:'Node 03', role:'pH', planned:true},
    {key:'Node 04', role:'Turbidity', planned:true},
    {key:'Node 05', role:'Electrical conductivity', planned:true},
    {key:'Camera 06', role:'RGB camera', planned:true},
    {key:'Node 07', role:'UV254 / Optical COD proxy', planned:true}
  ];
  for (const device of devices) {
    const row = document.createElement('tr'), name = document.createElement('th');
    name.scope = 'row'; name.textContent = device.name || device.key;
    const role = document.createElement('span'); role.className = 'network-role'; role.textContent = device.role;
    name.append(role); row.append(name);
    for (const [label, value] of [['IP address', addresses[device.key]], ['MAC address', device.mac || (device.planned ? 'Not assigned' : 'Not recorded')], ['Assignment', device.planned ? 'Planned' : 'Configured']]) {
      const cell = document.createElement('td'); cell.dataset.label = label; cell.textContent = value; row.append(cell);
    }
    el('network-rows').append(row);
  }
}
function setupTemperatures() {
  for (const m of temperatureMeasurements) {
    const row = document.createElement('tr'); row.id = `temperature-row-${m.id}`;
    const name = document.createElement('th'); name.scope = 'row';
    const link = document.createElement('a'); link.href = detailHref(m);
    link.textContent = `${m.probe} / ${m.node}`;
    const ip = document.createElement('span'); ip.className = 'device-ip'; ip.textContent = `IP: ${addresses[m.node]}`;
    name.append(link, ip); row.append(name);
    for (const [prefix, label] of [['reading', 'Temperature'], ['reading-time', 'Last received'], ['reading-state', 'Average participation']]) {
      const cell = document.createElement('td'); cell.id = `${prefix}-${m.id}`; cell.dataset.label = label;
      cell.textContent = '—'; row.append(cell);
    }
    el('temperature-rows').append(row);
  }
}
function renderTemperatures() {
  const now = paused ? pausedAt : Date.now();
  const readings = temperatureMeasurements.map(m => {
    const node = nodeFor(m), data = snapshots[node], latest = data?.latest, sample = latest?.sample;
    const value = sample?.[m.key];
    const age = data?.server_time + (now - fetchTimes[node]) / 1000 - latest?.received_at;
    const state = fetchErrors[node] ? 'Gateway unavailable' : !sample ? 'Waiting for data'
      : data.health?.storage_error ? 'Storage error'
      : !data.health?.mqtt_connected || !data.health?.subscription_ready ? 'Receiver disconnected'
      : sample.sensor_status !== 'OK' ? `Sensor: ${sample.sensor_status}`
      : !Number.isFinite(value) ? 'No temperature reading'
      : !Number.isFinite(age) || age < 0 || !(age <= data.stale_after_seconds) ? 'Stale reading' : '';
    el(`reading-${m.id}`).textContent = sample?.sensor_status === 'OK' && Number.isFinite(value) ? `${number(value)} °C` : '—';
    el(`reading-time-${m.id}`).textContent = Number.isFinite(latest?.received_at) ? date(latest.received_at) : '—';
    el(`reading-state-${m.id}`).textContent = state || 'Included';
    el(`temperature-row-${m.id}`).classList.toggle('is-excluded', Boolean(state));
    return {value, valid: !state};
  });
  const valid = readings.filter(r => r.valid);
  el('temperature-average').textContent = valid.length ? number(valid.reduce((sum, r) => sum + r.value, 0) / valid.length) : '—';
  el('temperature-count').textContent = `${valid.length} of ${readings.length} probes`;
  el('temperature-average-state').textContent = paused ? 'Display paused / Last displayed readings'
    : !valid.length ? 'No valid temperature readings. Check the probe status below.'
    : valid.length === 1 ? 'One valid probe only. This is its reading, not a multi-probe average.'
    : 'Mean of current probe readings.';
  el('temperature-view').dataset.state = paused ? 'paused' : valid.length ? 'ready' : 'unavailable';
  el('connection').textContent = paused ? 'Display paused' : valid.length === readings.length ? 'Receiving temperature readings'
    : valid.length ? 'Some temperature readings unavailable' : 'No current temperature readings';
  el('connection').className = paused ? '' : valid.length === readings.length ? 'good' : valid.length ? '' : 'error';
}
const predictionMeasurements = ['do', 'orp', 'temperature', 'temperature_orp'].map(id => measurements.find(m => m.id === id));
function setupPredictions() {
  for (const m of predictionMeasurements) {
    const row = document.createElement('tr'), name = document.createElement('th');
    name.scope = 'row';
    const link = document.createElement('a'); link.href = detailHref(m);
    link.textContent = m.id === 'orp' ? 'ORP' : m.id === 'temperature' ? 'Temperature (DO probe)' : m.name;
    const source = document.createElement('span'); source.className = 'prediction-source'; source.textContent = `${m.node} / ${addresses[m.node]}`;
    name.append(link, source); row.append(name);
    for (const field of ['current', 'forecast', 'difference']) {
      const cell = document.createElement('td'); cell.dataset.label = {current:'Latest reading', forecast:'12h forecast', difference:'Difference'}[field];
      const value = document.createElement('strong'); value.id = `prediction-${field}-${m.id}`; value.textContent = '—'; cell.append(value);
      if (field === 'current') { const state = document.createElement('span'); state.id = `prediction-source-state-${m.id}`; state.className = 'prediction-source'; cell.append(state); }
      row.append(cell);
    }
    el('prediction-rows').append(row);
  }
}
function renderPredictions() {
  const latest = predictionData?.latest;
  const now = predictionData ? predictionData.server_time + (Date.now() - predictionFetchTime) / 1000 : Date.now() / 1000;
  const generated = latest ? Date.parse(latest.generated_at) / 1000 : null;
  const stale = latest && (now - generated > 90 * 60 || predictionData.status === 'stale');
  const state = predictionFailed || predictionData?.status === 'error' ? 'error' : paused ? 'paused' : stale ? 'stale' : predictionData?.status || 'loading';
  const messages = {loading:'Loading prediction results…', waiting:'Waiting for LSTM results', ready:'Latest LSTM predictions', stale:'Update overdue / Showing the last prediction', paused:'Display paused / Predictions are not refreshing', error:latest?'Prediction service unavailable / Displayed forecasts may be old':'Prediction data unavailable / Check the gateway'};
  el('prediction-status').textContent = messages[state];
  el('prediction-view').dataset.state = state;
  el('prediction-generated').textContent = latest ? date(generated) : '—';
  el('prediction-target').textContent = latest ? new Date(latest.forecast_for).toLocaleString() : '—';
  el('prediction-model').textContent = latest ? `Model: ${latest.model_version} / Times shown in local browser time` : state === 'waiting' ? 'No LSTM results have been received. Hourly inference is not configured yet.' : '';
  for (const m of predictionMeasurements) {
    const node = nodeFor(m), data = snapshots[node], sample = data?.latest?.sample;
    const age = data?.latest ? data.server_time + (Date.now() - fetchTimes[node]) / 1000 - data.latest.received_at : Infinity;
    const sourceState = fetchErrors[node] ? 'Gateway unavailable' : paused ? 'Display paused' : data?.health.storage_error ? 'Storage error' : !data?.health.subscription_ready ? 'Receiver disconnected' : !sample ? 'Waiting for data' : sample.sensor_status !== 'OK' ? `Sensor: ${sample.sensor_status}` : age > data.stale_after_seconds ? 'Stale reading' : '';
    const current = sample?.sensor_status === 'OK' ? sample[m.key] : null;
    const forecast = latest?.values[m.id];
    const format = value => Number.isFinite(value) ? `${number(value)} ${m.unit}` : '—';
    el(`prediction-current-${m.id}`).textContent = format(current);
    el(`prediction-source-state-${m.id}`).textContent = sourceState;
    el(`prediction-forecast-${m.id}`).textContent = format(forecast);
    const difference = forecast - current;
    el(`prediction-difference-${m.id}`).textContent = state === 'ready' && !sourceState && Number.isFinite(current) && Number.isFinite(forecast) ? `${difference > 0 ? '+' : ''}${number(difference)} ${m.unit}` : '—';
  }
}
// Motion Prompt #057 · MIT License (c) 2026 Shohei Ohtaki · https://showheyohtaki.github.io/motion-prompt/#057
// Vertical sidebar adaptation; retain the 250 ms easeInOutCubic indicator motion.
function positionNavIndicator(animate = false) {
  const nav = el('sensor-nav'), active = nav.querySelector('[aria-current]');
  if (!active) return;
  let marker = el('nav-indicator');
  if (!marker) {
    marker = document.createElement('span'); marker.id = 'nav-indicator';
    marker.setAttribute('aria-hidden', 'true'); nav.append(marker);
  }
  const before = getComputedStyle(marker).transform;
  const box = active.getBoundingClientRect(), parent = nav.getBoundingClientRect();
  const mobile = matchMedia('(max-width: 760px)').matches;
  const x = box.left - parent.left + nav.scrollLeft;
  const y = box.top - parent.top + nav.scrollTop;
  marker.getAnimations().forEach(a => a.cancel());
  marker.style.transform = mobile
    ? `translate(${x}px, ${y + box.height - 4}px) scale(${box.width}, 4)`
    : `translate(${x}px, ${y}px) scale(4, ${box.height})`;
  if (animate && before !== 'none' && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    marker.animate([{transform: before}, {transform: marker.style.transform}],
      {duration: 250, easing: 'cubic-bezier(0.65, 0, 0.35, 1)'});
  }
}
function selectView() {
  const id=location.hash.slice(1) || 'overview';
  const m=measurements.find(m=>m.id===(id==='temperature_do'?'temperature':id));
  const temperature=id==='temperature', prediction=id==='predictions', network=id==='network', overview=!m && !prediction && !temperature && !network;
  el('overview').hidden=!overview; el('prediction-view').hidden=!prediction;
  el('network-view').hidden=!network;
  el('temperature-view').hidden=!temperature;
  el('live-detail').hidden=temperature || !m?.live; el('planned-view').hidden=!m || m.live;
  el('view-subtitle').textContent=m ? `${m.node}${m.live ? ' / IP: '+addresses[m.node] : ''}` : '';
  el('view-subtitle').hidden=!m || temperature;
  document.querySelector('.timestamp').hidden=prediction || temperature || network;
  const navId=temperature || m?.key==='temperature_c'?'temperature':overview?'overview':id;
  for(const a of el('sensor-nav').querySelectorAll('a')) {
    if(a.hash===`#${navId}`) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current');
  }
  positionNavIndicator(true);
  if(prediction) renderPredictions();
  if(temperature) {renderTemperatures();return;}
  el('temperature-source').hidden=id!=='temperature';
  if(m?.live) {
    activeMeasurement=m; el('detail-title').textContent=m.name;
    el('chart-title').textContent=`${m.name} history`;
    el('chart-caption').textContent=`Gateway receive time (${m.unit})`;
    showSelectedNode();
  } else if(m) {
    el('planned-title').textContent=m.name; el('planned-description').textContent=m.description;
    el('planned-facts').replaceChildren();
    for(const [label,value] of [['Device',m.node],['Planned IP',addresses[m.node]],['Readings','Not available'],['History','Not available']]) {
      const row=document.createElement('div'), dt=document.createElement('dt'), dd=document.createElement('dd');
      dt.textContent=label;dd.textContent=value;row.append(dt,dd);el('planned-facts').append(row);
    }
  }
}
function updateOverview() {
  const s=snapshots.node_01?.latest?.sample;
  for(const m of measurements.filter(m=>m.live)) {
    const node=nodeFor(m), data=snapshots[node], s=data?.latest?.sample;
    const age=data?.latest ? data.server_time+(Date.now()-fetchTimes[node])/1000-data.latest.received_at : Infinity;
    const state=fetchErrors[node]?'Gateway unavailable':paused?'Display paused':data?.health.storage_error?'Storage error':!data?.health.subscription_ready?'MQTT receiver disconnected':!s?'Waiting for data':age>data.stale_after_seconds?'Telemetry stale':s.sensor_status!=='OK'?`Sensor: ${s.sensor_status}`:'';
    el(`value-${m.id}`).textContent=s?.sensor_status==='OK'?`${number(s[m.key])} ${m.unit}`:'—';
    el(`state-${m.id}`).hidden=!state;
    el(`state-${m.id}`).textContent=state;
  }
  el('overview-status').textContent='Calibration and compensation remain unverified. Each measurement shows its own connection status.';
}
setupNavigation();
setupNetwork();
setupTemperatures();
setupPredictions();
selectView();
new ResizeObserver(() => positionNavIndicator()).observe(el('sensor-nav'));
document.fonts.ready.then(() => positionNavIndicator());
window.addEventListener('hashchange',()=>{selectView();el('main').focus();});

function freshness() {
  if(!el('prediction-view').hidden) renderPredictions();
  if (!last) { updateOverview(); if(!el('temperature-view').hidden)renderTemperatures(); return; }
  const elapsed = (Date.now() - lastFetch) / 1000;
  const age = last.latest ? Math.max(0, last.server_time + elapsed - last.latest.received_at) : null;
  const stale = age !== null && age > last.stale_after_seconds;
  el('age').textContent = age === null ? 'Waiting for telemetry' : `${Math.floor(age)}s since last reception`;
  const h = last.health;
  el('connection').textContent = failed ? 'Gateway unavailable; displayed values may be old' : paused ? 'Display paused' : h.storage_error ? 'Storage error' : !h.subscription_ready ? 'MQTT receiver disconnected or subscription pending' : stale ? 'Telemetry stale' : last.latest ? 'Receiving telemetry' : 'Waiting for telemetry';
  el('connection').className = failed || h.storage_error || !h.subscription_ready ? 'error' : paused || stale || !last.latest ? '' : 'good';
  document.body.dataset.readingState = failed || stale || paused ? 'old' : 'current';
  updateOverview();
  el('sample-state').textContent = last.latest ? (failed || stale || paused ? 'Last stored reading' : 'Latest received reading') : 'No sample';
  if(!el('temperature-view').hidden)renderTemperatures();
}
function chart(data) {
  const svg = el('chart'); svg.replaceChildren();
  const width = Math.max(280, svg.getBoundingClientRect().width);
  svg.setAttribute('viewBox', `0 0 ${width} 240`);
  const rows = data.history, end = data.server_time, start = end - Number(el('window').value) * 60;
  const values = rows.filter(r => r.sample.sensor_status === 'OK' && Number.isFinite(r.sample[activeMeasurement.key])).map(r => r.sample[activeMeasurement.key]);
  const spec=accuracy[activeMeasurement.id], margin=spec?.delta || 0;
  el('chart-caption').textContent=`Gateway receive time (${activeMeasurement.unit})${spec ? '; Shading: manufacturer spec '+spec.note+' (not verified uncertainty)' : ''}`;
  const low = values.length ? Math.min(...values)-margin-0.5 : 0;
  const high = values.length ? Math.max(low+1, Math.max(...values)+margin+0.5) : 10;
  const make = (tag, attrs) => {const n=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));svg.append(n);return n;};
  for(let i=0;i<4;i++) {const y=15+i*65;make('line',{x1:55,x2:width-15,y1:y,y2:y,stroke:'#d7e1e8'});const t=make('text',{x:0,y:y+5,fill:'#526779','font-size':14});t.textContent=(high-i*(high-low)/3).toFixed(1);}
  const bands=make('g',{'class':'accuracy-bands','aria-hidden':'true'});
  let segment=[];
  const flushBand=()=>{
    if(!segment.length || !margin){segment=[];return;}
    const offset=margin/(high-low)*195;
    const polygon=document.createElementNS(svg.namespaceURI,'polygon');
    let points=segment;
    if(points.length===1) points=[{x:points[0].x-2.5,y:points[0].y},{x:points[0].x+2.5,y:points[0].y}];
    polygon.setAttribute('points',[...points.map(p=>`${p.x},${p.y-offset}`),...points.slice().reverse().map(p=>`${p.x},${p.y+offset}`)].join(' '));
    polygon.setAttribute('fill','#17657b');polygon.setAttribute('fill-opacity','0.18');bands.append(polygon);segment=[];
  };
  let path='', previous=null;
  for (const row of rows) {
    const s=row.sample;
    if(s.sensor_status!=='OK'||!Number.isFinite(s[activeMeasurement.key])){flushBand();previous=null;continue;}
    const x=55+(row.received_at-start)/(end-start)*(width-70), y=15+(high-s[activeMeasurement.key])/(high-low)*195;
    const join=previous && row.received_at-previous.received_at<=20 && s.boot_id===previous.sample.boot_id && s.sequence===previous.sample.sequence+1;
    if(!join)flushBand();
    segment.push({x,y});
    path+=`${join?'L':'M'}${x.toFixed(2)},${y.toFixed(2)} `;
    const dot=make('circle',{cx:x,cy:y,r:2.5,fill:'#17657b'});
    const title=document.createElementNS(svg.namespaceURI,'title');title.textContent=`${date(row.received_at)}: ${number(s[activeMeasurement.key])} ${activeMeasurement.unit}`;dot.append(title);previous=row;
  }
  flushBand();
  make('path',{d:path,fill:'none',stroke:'#17657b','stroke-width':2});
  el('empty').hidden=values.length>0;
  svg.setAttribute('aria-label',values.length?`${activeMeasurement.name}: ${values.length} valid readings. See recent readings table below.`:`No valid ${activeMeasurement.name.toLowerCase()} readings in this window`);
  el('start').textContent=new Date(start*1000).toLocaleTimeString();el('end').textContent=new Date(end*1000).toLocaleTimeString();
}
function render(data) {
  const s=data.latest?.sample;
  const orp=nodeFor(activeMeasurement)==='node_02';
  document.querySelector('.primary-reading > span').textContent=orp?'Oxidation–reduction potential':'Dissolved oxygen';
  document.querySelector('.primary-reading .unit').textContent=orp?'mV':'mg/L';
  document.querySelector('#sat').closest('div').hidden=orp;
  document.querySelector('#live-detail thead th:nth-child(2)').textContent=orp?'ORP (mV)':'DO (mg/L)';
  document.querySelector('.details p').textContent=`${orp?'ORP':'DO'} probe → ${activeMeasurement.node} → MQTT → SQLite`;
  el('temperature-source').hidden=!activeMeasurement.id.startsWith('temperature');
  el('temperature-source').textContent=`Source: ${activeMeasurement.node} / ${orp?'ORP':'DO'} probe`;
  for (const [id,key] of [['do',orp?'orp_mv':'do_mg_l'],['temp','temperature_c'],['sat','saturation_pct']]) el(id).textContent=number(s?.[key]);
  el('received').textContent=data.latest?date(data.latest.received_at):'No samples yet';
  for (const [id,key] of [['sensor','sensor_status'],['clock','clock_status'],['calibration','calibration_status'],['compensation','compensation_status'],['sequence','sequence'],['missed','not_forwarded_before_sample'],['firmware','firmware_version']]) {el(id).textContent=s?.[key]??'—';el(id).dataset.state=s?.[key]??'UNKNOWN';}
  el('notice').textContent=!s?'Waiting for the first stored reading. No simulated data is displayed.':s.sensor_status!=='OK'?`Sensor reports ${s.sensor_status}. Invalid measurements remain missing.`:`${s.clock_status==='UNSYNCED'?'Node clock is unsynchronized. ':''}History uses gateway receive time, not sample time. Calibration: ${s.calibration_status}; compensation: ${s.compensation_status}.`;
  el('pipeline').textContent=data.health.storage_error?'SQLite write failed; recording needs attention':data.health.subscription_ready?'MQTT subscription active; readings committed to SQLite before acknowledgment':'MQTT subscription pending; showing stored history';
  chart(data);el('rows').replaceChildren();
  for(const r of data.history.slice(-20).reverse()){const tr=document.createElement('tr');for(const text of [date(r.received_at),number(r.sample[orp?'orp_mv':'do_mg_l']),number(r.sample.temperature_c),r.sample.sensor_status]){const td=document.createElement('td');td.textContent=text;tr.append(td);}el('rows').append(tr);}
  freshness();
}
function showSelectedNode() {
  const node=nodeFor(activeMeasurement);
  last=snapshots[node] || {latest:null, history:[], server_time:Date.now()/1000, health:{}, stale_after_seconds:20};
  lastFetch=fetchTimes[node] || Date.now(); failed=Boolean(fetchErrors[node]); render(last);
}
async function refresh() {
  if(paused||busy||document.hidden)return;
  busy=true;
  const nodeRequests=[...new Set(measurements.filter(m=>m.live).map(nodeFor))].map(async node => {
    try {
      const response=await fetch(`/api/${node}?minutes=${el('window').value}`,{signal:AbortSignal.timeout(5000)});
      if(!response.ok)throw new Error('Gateway unavailable');
      const data=await response.json(); if(paused)return;
      snapshots[node]=data;fetchTimes[node]=Date.now();fetchErrors[node]=false;
    } catch { if(!paused)fetchErrors[node]=true; }
  });
  await Promise.all([...nodeRequests, refreshPredictions()]);
  busy=false; if(!paused)showSelectedNode();
}
async function refreshPredictions() {
  try {
    const response=await fetch('/api/predictions',{signal:AbortSignal.timeout(5000)});
    if(!response.ok)throw new Error('Prediction service unavailable');
    const data=await response.json();
    if(!['waiting','ready','stale','error'].includes(data.status) || !Number.isFinite(data.server_time))throw new Error('Invalid prediction response');
    if(['ready','stale'].includes(data.status) && (!data.latest?.values || !Number.isFinite(Date.parse(data.latest.generated_at)) || !Number.isFinite(Date.parse(data.latest.forecast_for))))throw new Error('Missing prediction result');
    if(paused)return;
    predictionData=data;predictionFetchTime=Date.now();predictionFailed=false;
  } catch { if(!paused)predictionFailed=true; }
}
function setPaused(value) {
  if(value && !paused)pausedAt=Date.now();
  paused=value;
  for(const id of ['pause','prediction-pause','temperature-pause']) {el(id).textContent=paused?'Resume display':'Pause display';el(id).setAttribute('aria-pressed',String(paused));}
  freshness();if(!paused)refresh();
}
el('window').addEventListener('change',()=>setPaused(false));
for(const id of ['pause','prediction-pause','temperature-pause']) el(id).addEventListener('click',()=>setPaused(!paused));
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
setInterval(refresh,5000);setInterval(freshness,1000);refresh();

let resizeFrame;
window.addEventListener('resize',()=>{cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>{if(last)chart(last);});});
