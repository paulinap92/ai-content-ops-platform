// Read-only canonical data browser. Values always enter the DOM as text.
const make=(tag,text,attrs={})=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;};
const short=v=>v===null||v===undefined?'—':typeof v==='object'?JSON.stringify(v):String(v);
const stamp=v=>!v?'—':Number.isNaN(new Date(v).getTime())?String(v):new Intl.DateTimeFormat('pl-PL',{dateStyle:'medium',timeStyle:'short'}).format(new Date(v));
const names={id:'ID',title:'Tytuł',name:'Nazwa',resource:'Rodzaj',target:'Wyspa / zakres',available:'Dostępne',status:'Stan',source:'Źródło',source_updated_at:'Aktualizacja źródła',ingested_at:'Zapis w bazie',observed_at:'Czas pomiaru',occurred_at:'Czas zdarzenia',magnitude:'Magnituda',depth_km:'Głębokość (km)',payload:'Dane',dataset:'Zestaw danych',point_id:'Punkt',temperature:'Temperatura',precipitation:'Opady',latitude:'Szerokość',longitude:'Długość'};
export function createInspector({root,api,label,onIsland}){
 let epoch=0,coverageCache=null;
 function begin(title,help){const id=++epoch;root.replaceChildren(make('h2',title),make('p',help,{class:'view-help'}));return id;}
 function notice(text,error=false){root.append(make('p',text,{class:error?'inspection-error':'inspection-note'}));}
 function details(value,title='Szczegóły rekordu'){
  const d=make('dialog',undefined,{class:'data-dialog'});const close=make('button','Zamknij',{type:'button'});close.onclick=()=>{d.close();d.remove();};d.append(close,make('h2',title),make('pre',JSON.stringify(value,null,2)));document.body.append(d);d.showModal();
 }
 function grid(rows,columns){
  if(!rows.length)return make('p','Brak rekordów dla tego wyboru.',{class:'empty-state'});
  const wrap=make('div',undefined,{class:'data-grid-scroll'}),table=make('table',undefined,{class:'data-grid'}),head=make('tr');
  const cols=columns?.length?columns.map(c=>typeof c==='string'?c:c.name):[...new Set(rows.flatMap(r=>Object.keys(r)))];
  for(const key of cols)head.append(make('th',names[key]||key));const thead=make('thead');thead.append(head);table.append(thead);const body=make('tbody');
  for(const row of rows){const tr=make('tr');for(const key of cols){const td=make('td');const value=row[key];if(typeof value==='object'&&value!==null){const b=make('button',Array.isArray(value)?`Lista (${value.length}) · otwórz`:'JSON · otwórz',{type:'button',class:'json-cell'});b.onclick=()=>details(value,names[key]||key);td.append(b);}else {td.textContent=short(value);td.title=short(value);}tr.append(td);}const inspect=make('td'),b=make('button','Szczegóły',{type:'button',class:'json-cell'});b.onclick=()=>details(row);inspect.append(b);tr.append(inspect);body.append(tr);}head.append(make('th','Rekord'));table.append(body);wrap.append(table);return wrap;
 }
 async function getCoverage(refresh=false){if(!coverageCache||refresh)coverageCache=await api('/coverage');return coverageCache;}
 function islandButtons(entry,section,resource){const box=make('div',undefined,{class:'availability-islands'});for(const island of ['tenerife','gran-canaria','lanzarote','fuerteventura','la-palma','la-gomera','el-hierro','la-graciosa']){const count=entry?.islands?.[island]||0;const b=make('button',`${label(island)} · ${count}`,{type:'button',class:count?'has-data':'no-data'});b.onclick=()=>onIsland(island,section,resource);box.append(b);}return box;}
 async function showCoverage(section=null,resource=null){
  const id=begin(section?'Dostępność na wyspach':'Kompletność danych','Widok pokazuje rzeczywiste rekordy w bazie. Zero oznacza brak wpisów w danym zakresie, a nie błąd edytora.');
  try{const data=await getCoverage();if(id!==epoch)return;
   const refresh=make('button','Odśwież zestawienie',{type:'button'});refresh.onclick=async()=>{coverageCache=null;await showCoverage(section,resource);};root.append(refresh);
   if(section){const key=resource==='featured'?'explore':resource;const entry=section==='explore'&&resource==='featured'?data.guide.explore:section==='guide'?data.guide[key]:section==='explore'?data.explore[key]:null;
    if(entry){root.append(make('h3',`${resource==='featured'?'Destacados':label(resource)} · w bazie ${entry.total}`),islandButtons(entry,section,resource));}
    else if(section==='calendar'){const totals={};for(const r of data.calendar)totals[r.island]=(totals[r.island]||0)+r.count;root.append(islandButtons({islands:totals},section,null),make('h3','Dostępne miesiące'),grid(data.calendar,['island','month','count']));}
    else root.append(make('p','Wybierz wyspę w panelu po lewej, aby otworzyć tę część strony.'));
    return;
   }
   for(const [title,entries] of [['Explore — katalogi miejsc',data.explore],['Guía i Destacados — artykuły',data.guide]]){
    root.append(make('h3',title));const rows=Object.entries(entries).map(([key,v])=>({category:key==='explore'?'Destacados':label(key),total:v.total,...Object.fromEntries(data.islands.map(i=>[i,v.islands[i]||0]))}));root.append(grid(rows,['category','total',...data.islands]));
   }
   for(const [title,rows] of [['Kalendarz — wydarzenia według miesiąca',data.calendar],['Live — dostępne migawki',data.live],['Datos — pomiary i zakres historii',data.climate],['Datos — zestawy statystyczne',data.statistics]])root.append(make('h3',title),grid(rows));
   notice(data.notes);
  }catch(e){if(id===epoch)notice(e.message,true);}
 }
 async function emptyHint(section,resource,island){
  const data=await getCoverage();const entry=section==='explore'&&resource==='featured'?data.guide.explore:section==='guide'?data.guide[resource]:data.explore[resource];
  const box=make('div',undefined,{class:'empty-availability'});box.append(make('strong',`Brak wpisów dla ${label(island)}. W całej bazie: ${entry?.total||0}.`),islandButtons(entry,section,resource));return box;
 }
 async function showDatabase(){
  const id=begin('Baza danych · PostgreSQL','Zwykła przeglądarka tabel bazy strony (schemat design). Odczyt, wyszukiwanie, sortowanie i paginacja; nie zmienia danych.');
  try{const meta=await api('/database/tables');if(id!==epoch)return;const controls=make('div',undefined,{class:'inspection-toolbar'}),select=make('select',undefined,{'aria-label':'Tabela bazy danych'}),column=make('select',undefined,{'aria-label':'Kolumna wyszukiwania'}),query=make('input',undefined,{placeholder:'Szukaj wartości w wybranej kolumnie…','aria-label':'Szukaj w tabeli'}),order=make('select',undefined,{'aria-label':'Kierunek sortowania'});const sortBy=make('select',undefined,{'aria-label':'Kolumna sortowania'});sortBy.append(new Option('Klucz główny',''));order.append(new Option('Rosnąco','asc'),new Option('Malejąco','desc'));for(const t of meta.tables)select.append(new Option(t.name,t.name));
   const refresh=make('button','Odśwież',{type:'button'});controls.append(select,column,query,sortBy,order,refresh);const info=make('p','Wczytywanie…',{class:'inspection-note'}),body=make('div'),pager=make('div',undefined,{class:'inspection-toolbar'}),prev=make('button','← Poprzednie',{type:'button'}),next=make('button','Następne →',{type:'button'});pager.append(prev,next);root.append(controls,info,body,pager);let offset=0,timer,sequence=0;
   async function load(){const request=++sequence;info.textContent='Wczytywanie tabeli…';try{const p=new URLSearchParams({offset,limit:25,q:query.value,direction:order.value});if(column.value)p.set('column',column.value);if(sortBy.value)p.set('sort',sortBy.value);const d=await api('/database/tables/'+encodeURIComponent(select.value)+'?'+p);if(id!==epoch||request!==sequence)return;const selected=column.value;column.replaceChildren(new Option('Kolumna tekstowa (automatycznie)',''),...d.columns.map(c=>new Option(`${c.name} · ${c.type}`,c.name)));column.value=selected;const ordered=sortBy.value;sortBy.replaceChildren(new Option("Klucz główny",""),...d.columns.map(c=>new Option(c.name,c.name)));sortBy.value=ordered;body.replaceChildren(grid(d.rows,d.columns));info.textContent=`design.${d.table} · ${d.count} rekordów · ${offset+1> d.count?0:offset+1}–${Math.min(offset+d.rows.length,d.count)} · tylko odczyt`;prev.disabled=offset===0;next.disabled=offset+d.rows.length>=d.count;}catch(e){info.textContent=e.message;}}
   select.onchange=()=>{offset=0;query.value='';column.value='';sortBy.value='';load();};column.onchange=()=>{offset=0;load();};order.onchange=()=>{offset=0;load();};sortBy.onchange=()=>{offset=0;load();};query.oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{offset=0;load();},350);};refresh.onclick=()=>load();prev.onclick=()=>{offset=Math.max(0,offset-25);load();};next.onclick=()=>{offset+=25;load();};await load();
  }catch(e){if(id===epoch)notice(e.message,true);}
 }
 async function showData(section,resource,island){
  const id=begin(`${section==='live'?'Live':section==='datos'?'Datos':'Transporte'} / ${label(resource)}`,'Dane źródłowe z bazy strony. Możesz je przeglądać; aktualizują je joby. Teksty i widoczność pozostają w edytorze tej części strony.');
  const controls=make('div',undefined,{class:'inspection-toolbar'}),metrics=make('select',undefined,{'aria-label':'Zestaw pomiarów'}),refresh=make('button','Odśwież dane',{type:'button'}),all=make('button','Cały archipelag',{type:'button'});metrics.append(new Option('Wszystkie rodzaje',''));controls.append(metrics,refresh,all);const info=make('div',undefined,{class:'data-summary'}),body=make('div'),pager=make('div',undefined,{class:'inspection-toolbar'}),prev=make('button','← Poprzednie',{type:'button'}),next=make('button','Następne →',{type:'button'});pager.append(prev,next);root.append(controls,info,body,pager);let offset=0,metric='',scope=island,seq=0;
  async function load(){const token=++seq;try{const p=new URLSearchParams({section,resource,island:scope,offset,limit:25});if(metric)p.set('metric',metric);const d=await api('/data?'+p);if(id!==epoch||token!==seq)return;metrics.replaceChildren(new Option('Wszystkie rodzaje',''),...(d.metrics||[]).map(v=>new Option(v,v)));metrics.value=d.metric||metric;metrics.hidden=!(d.metrics?.length);const updated=d.rows[0]?.observed_at||d.rows[0]?.occurred_at||d.rows[0]?.source_updated_at||d.rows[0]?.ingested_at;info.replaceChildren(make('strong',`${d.count} rekordów · ${scope==='global'?'cały archipelag':label(scope)}`),make('span',`Tabela: ${d.table} · ostatni zapis w widoku: ${stamp(updated)}`));body.replaceChildren();if(d.reason)body.append(make('p',d.reason,{class:'inspection-note'}));
    if(d.table==='live_snapshots'){for(const snapshot of d.rows){const payload=snapshot.payload||{};const points=payload.points||payload.items||payload.features;body.append(make('h3',`${label(snapshot.target||scope)} · ${snapshot.status||'migawka'}`));if(Array.isArray(points)&&points.length)body.append(grid(points.map(p=>p.properties?{...p.properties,geometry:p.geometry}:p)));}}
    body.append(grid(d.rows,d.columns));prev.disabled=offset===0;next.disabled=offset+d.rows.length>=d.count;
   }catch(e){if(id===epoch)body.replaceChildren(make('p',e.message,{class:'inspection-error'}));}}
  metrics.onchange=()=>{metric=metrics.value;offset=0;load();};refresh.onclick=()=>load();all.onclick=()=>{scope='global';offset=0;load();};prev.onclick=()=>{offset=Math.max(0,offset-25);load();};next.onclick=()=>{offset+=25;load();};await load();
 }
 return {showCoverage,showDatabase,showData,emptyHint,getCoverage,cancel:()=>{epoch++;root.replaceChildren();}};
}

export function renderMonth(root,items,month,onSelect){
 root.replaceChildren();const [year,m]=month.split('-').map(Number);if(!year||!m)return;
 const first=new Date(Date.UTC(year,m-1,1)),start=new Date(first);start.setUTCDate(1-(first.getUTCDay()+6)%7);
 const title=new Intl.DateTimeFormat('pl-PL',{month:'long',year:'numeric',timeZone:'UTC'}).format(first);
 root.append(make('h3',title));const grid=make('div',undefined,{class:'calendar-month','aria-label':'Kalendarz miesiąca'});
 for(const name of ['Pon','Wt','Śr','Czw','Pt','Sob','Niedz'])grid.append(make('div',name,{class:'calendar-weekday'}));
 for(let i=0;i<42;i++){const day=new Date(start);day.setUTCDate(start.getUTCDate()+i);const key=day.toISOString().slice(0,10),cell=make('div',undefined,{class:'calendar-day'+(day.getUTCMonth()!==m-1?' outside':'')});cell.append(make('time',String(day.getUTCDate()),{datetime:key}));
  for(const item of items){const p=item.draft;const a=String(p.start_date||p.start_at||'').slice(0,10),b=String(p.end_date||p.end_at||a).slice(0,10);if(a&&key>=a&&key<=b){const button=make('button',p.title||p.name||'Wydarzenie',{type:'button',class:'calendar-event',title:(p.location||p.location_name||'')});button.onclick=()=>onSelect(item);cell.append(button);}}
  grid.append(cell);
 }
 root.append(grid);
 if(!items.length)root.append(make('p','Brak wydarzeń w tym miesiącu. Zmień miesiąc lub wyspę; puste dni nie oznaczają awarii edytora.',{class:'empty-state'}));
}
