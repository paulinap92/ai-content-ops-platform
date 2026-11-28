// Demand-driven monitor. No setInterval, scheduler, source fetch or DB access.
const root=document.querySelector('#data-monitor');
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=v=>v?new Intl.DateTimeFormat('es-ES',{dateStyle:'short',timeStyle:'short'}).format(new Date(v)):'Sin dato';
const bytes=v=>Number.isFinite(Number(v))?new Intl.NumberFormat('es-ES',{maximumFractionDigits:2}).format(Number(v)/1048576)+' MiB':'No medido';
const statusLabel=value=>({running:"En curso",disabled:"Desactivado",blocked:"Bloqueado",succeeded:"Correcto",failed:"Error",abandoned:"Interrumpido",pending:"Pendiente",deferred:"Aplazado"}[value]??value);
let state=null;
async function get(path='') {
 const response=await fetch('/site/api/data-monitor'+path,{headers:{Accept:'application/json'},credentials:'same-origin',cache:'no-store'});
 if(!response.ok) throw new Error('No se puede consultar el monitor ('+response.status+'). No se consulta otra fuente.');
 return response.json();
}
function renderRows() {
 if(!state)return;
 const q=document.querySelector('#monitor-search').value.toLowerCase(),domain=document.querySelector('#monitor-domain').value,status=document.querySelector('#monitor-status').value;
 const rows=state.items.filter(r=>(!q||[r.name,r.source_id,...r.products.map(p=>p.product_id)].join(' ').toLowerCase().includes(q))&&(!domain||r.domains.includes(domain))&&(!status||r.status===status));
 document.querySelector('#monitor-count').textContent=rows.length+' / '+state.items.length+' jobs';
 document.querySelector('#monitor-rows').innerHTML=rows.map(r=>`<tr><td><button type="button" data-monitor-job="${esc(r.job_id)}">${esc(r.name)}</button></td><td>${esc(r.source_id)}</td><td>${r.products.map(p=>esc(p.product_id.replace('cc:product:',''))).join('<br>')}</td><td>${esc(r.interval_seconds/60)} min · ${r.enabled?'activo':'desactivado'}</td><td>${esc(statusLabel(r.status))}</td><td>${date(r.last_success_at)}</td><td>${date(r.next_scheduled_at)}</td><td>${r.duration_ms==null?'—':esc(r.duration_ms)+' ms'}</td><td>${esc(r.inserted)} / ${esc(r.changed)}</td><td>${esc(r.error_message)}</td><td>${r.history.map(h=>`${esc(h.resolution)}: ${date(h.from_at)} → ${date(h.through_at)}`).join('<br>')||'Sin datos locales'}</td></tr>`).join('');
}
async function load() {
 document.querySelector('#monitor-message').textContent='Consultando último estado SQL…';
 try {
  state=await get();
  const summary=state.summary;
  document.querySelector('#monitor-kpis').innerHTML=[['Jobs activos',summary.active_jobs],['Actualizaciones correctas',summary.successful_updates],['Errores',summary.errors],['Productos desactualizados',summary.stale_products],['Sin inicializar',summary.uninitialized_products]].map(([label,value])=>`<div class="monitor-kpi"><small>${esc(label)}</small><strong>${esc(value)}</strong></div>`).join('');
  document.querySelector('#monitor-message').textContent='Lectura: '+date(state.checked_at)+'. '+state.note;
  const domains=[...new Set(state.items.flatMap(r=>r.domains))].sort();
  document.querySelector('#monitor-domain').innerHTML='<option value="">Todas las áreas</option>'+domains.map(d=>`<option>${esc(d)}</option>`).join('');
  document.querySelector('#monitor-status').innerHTML='<option value="">Todos los estados</option>'+[...new Set(state.items.map(r=>r.status))].sort().map(d=>`<option value="${esc(d)}">${esc(statusLabel(d))}</option>`).join('');
  renderRows();
 }catch(e){document.querySelector('#monitor-message').textContent=e.message;}
}
async function detail(job) {
 const box=document.querySelector('#monitor-detail');box.hidden=false;box.textContent='Cargando detalle…';
 try {
  const data=await get('/jobs/'+encodeURIComponent(job)),r=data.job;
  box.innerHTML=`<h2>${esc(r.name)}</h2><p>${esc(r.operation_note)}. ${esc(r.blocked_reason)}</p><p>Consumidores: ${r.products.map(p=>[p.live?'Live':'',p.datos.length?'Datos ('+p.datos.length+')':'',p.observatorio?'Observatorio '+p.observatorio:''].filter(Boolean).map(esc).join(' · ')).join('; ')}</p><button type="button" id="monitor-run" disabled title="Desactivado por defecto; requiere autorización y queue central">Solicitar ejecución manual</button><p>La solicitud no activa el horario ni crea otro importador.</p><h3>Últimas ${data.runs.length} ejecuciones</h3><div class="monitor-scroll"><table><thead><tr><th>Inicio</th><th>Final</th><th>Estado</th><th>Duración</th><th>Nuevos / cambios</th><th>Error</th></tr></thead><tbody>${data.runs.map(x=>`<tr><td>${date(x.started_at)}</td><td>${date(x.finished_at)}</td><td>${esc(statusLabel(x.status))}</td><td>${esc(x.duration_ms)} ms</td><td>${esc(x.inserted)} / ${esc(x.changed)}</td><td>${esc(x.error_category)}</td></tr>`).join('')}</tbody></table></div>`;
  // Availability is controlled independently by BOTH authenticated servers.
  if(r.manual_available===true) {
   const button=document.querySelector('#monitor-run');button.disabled=false;
   const key=crypto.randomUUID();
   button.onclick=async()=>{button.disabled=true;try{const response=await fetch('/site/api/data-monitor/jobs/'+encodeURIComponent(job)+'/requests',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({idempotency_key:key})});if(!response.ok)throw new Error('Solicitud rechazada ('+response.status+')');button.textContent='Solicitud en la cola central';}catch(e){button.textContent=e.message;}};
  }
 }catch(e){box.textContent=e.message;}
}
async function capacity() {
 const box=document.querySelector('#monitor-capacity');box.hidden=false;box.textContent='Consultando agregados SQL…';
 try {const c=await get('/capacity');box.innerHTML=`<h2>Capacidad y retención</h2><p>${esc(c.scope_note)}</p><p>Base local: ${bytes(c.database_bytes)} · lectura ${date(c.checked_at)} · eliminación automática: desactivada</p><div class="monitor-scroll"><table><thead><tr><th>Área</th><th>Observaciones</th><th>Bytes de filas atribuidos</th><th>Resolución</th><th>Desde</th><th>Hasta</th></tr></thead><tbody>${c.domains.map(x=>`<tr><td>${esc(x.domain)}</td><td>${esc(x.observations)}</td><td>${bytes(x.attributed_row_bytes)}</td><td>${esc(x.resolutions.join(', '))}</td><td>${date(x.from_at)}</td><td>${date(x.through_at)}</td></tr>`).join('')}</tbody></table></div><h3>Dry-run — ninguna eliminación</h3><table><thead><tr><th>Recurso</th><th>Candidatos</th><th>Bytes de filas</th><th>Protecciones</th></tr></thead><tbody>${c.dry_run.map(x=>`<tr><td>${esc(x.resource)}</td><td>${esc(x.candidates)}</td><td>${bytes(x.bytes)}</td><td>${esc(x.protected_reason)}</td></tr>`).join('')}</tbody></table><details><summary>Políticas, tablas físicas y métricas de infraestructura con fecha</summary><pre>${esc(JSON.stringify({retention:c.retention,physical_relations:c.physical_relations,infrastructure:c.infrastructure,raw_compaction:c.raw_compaction},null,2))}</pre></details>`;}catch(e){box.textContent=e.message;}
}
for(const id of ['monitor-search','monitor-domain','monitor-status'])document.querySelector('#'+id).addEventListener('input',renderRows);
document.querySelector('#monitor-refresh').onclick=load;
document.querySelector('#monitor-capacity-load').onclick=capacity;
root.addEventListener('click',e=>{const b=e.target.closest('[data-monitor-job]');if(b)detail(b.dataset.monitorJob);});
load();
