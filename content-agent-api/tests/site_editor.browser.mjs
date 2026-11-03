// Browser regression for real editor assets; all API calls use isolated fixtures.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve,extname} from 'node:path';
import {chromium} from 'playwright';

const assets=fileURLToPath(new URL('../canarias_site/studio/',import.meta.url));
const staticAssets=fileURLToPath(new URL('../static/',import.meta.url));
const defaults=JSON.parse(await readFile(resolve(assets,'default_copy.json'),'utf8'));
const config={global:{sections:{},features:{},copy:{'home.title':'Hola, somos las Islas Canarias.'}},islands:{}};
const identity={kind:'settings',island:'global',resource:'site',record_key:'site'};
const settings={id:'settings-fixture',identity,version:1,status:'published',draft:config,published:config,base_fingerprint:'0'.repeat(64)};
const requests=[],writes=[];const uploaded=[];let optionalHealthFailure=true;
const options={islands:['el-hierro','la-palma','la-gomera','tenerife','gran-canaria','fuerteventura','lanzarote','la-graciosa'],sections:{explore:'Explore',live:'Live',calendar:'Calendario',news:'Noticias',datos:'Datos',guide:'Guía'},features:{guide:['crafts','culture','history','food','geology','nature'],explore:['places','beaches','food-producers','diving-spots','routes','fauna','flora','airports','ports','ferries','titsa-stops','titsa-routes','tilp-routes'],live:['weather','air-quality','marine','tides','alerts','seismic','volcanic','webcams','live-beaches'],datos:['climate','tourism','geology','economy']},copy_defaults:{'home.title':'Hola, somos las Islas Canarias.','home.description':'Ocho islas, miles de lugares por descubrir.','island.description':'','nav.guide':'Guía',...defaults}};
const coverageFixture={islands:options.islands,explore:{'food-producers':{total:9,islands:{'gran-canaria':3,fuerteventura:6}},'diving-spots':{total:1,islands:{'el-hierro':1}},places:{total:8,islands:{tenerife:1}}},guide:{history:{total:8,islands:Object.fromEntries(options.islands.map(i=>[i,1]))},explore:{total:48,islands:Object.fromEntries(options.islands.map(i=>[i,6]))}},calendar:[{island:'tenerife',month:'2026-11',count:3}],live:[{resource:'weather',island:'tenerife',available:true,status:'ok',updated_at:'2026-11-03T06:00:00Z'}],climate:[{resource:'weather',island:'tenerife',count:24,first:'2026-11-02T06:00:00Z',last:'2026-11-03T06:00:00Z'}],statistics:[],notes:'Synthetic fixture, no hosted database.'};
const server=createServer(async(req,res)=>{
 const url=new URL(req.url,'http://localhost');const path=url.pathname;
 if(path==='/health/ready'){res.setHeader('Content-Type','application/json');res.end('{"status":"ok"}');return;}
 if(path==='/health'){res.writeHead(optionalHealthFailure?500:200,{'Content-Type':'application/json'});res.end(JSON.stringify(optionalHealthFailure?{detail:'optional configuration unavailable'}:{photo_source:'drive',ai_configured:false,content_languages:['es','en','pl']}));return;}
 if(path==='/api/v1/content'){res.setHeader('Content-Type','application/json');res.end('[]');return;}
 if(path==='/' || path.startsWith('/static/')){
  const name=path==='/'?'index.html':path.slice('/static/'.length);
  if(!['index.html','styles.css','app.js','studio-extras.js'].includes(name)){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css'})[extname(name)]);res.end(await readFile(resolve(staticAssets,name)));return;
 }
 if(path==='/api/v1/events/sources'){res.setHeader('Content-Type','application/json');res.end('[]');return;}
 if(path==='/api/v1/photos/folders'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify([{path:'',total_count:1},{path:'Tenerife',total_count:1},{path:'Tenerife/Explore',total_count:1},{path:'Tenerife/Explore/volcanoes',total_count:1}]));return;}
 if(path==='/api/v1/photos' || path==='/api/v1/photos/drive-1'){res.setHeader('Content-Type','application/json');const photo={photo_id:'drive-1',current_name:'Teide.jpg',source:'drive',status:'approved',folder_path:'Tenerife/Explore/volcanoes',island:'Tenerife',site_area:'Explore',site_section:'volcanoes',alt_texts:{es:'Teide'},tags:[],web_view_link:'https://drive.google.com/file/d/fixture'};res.end(JSON.stringify(path.endsWith('drive-1')?photo:[photo]));return;}
 if(path==='/api/v1/photos/drive-1/preview'){res.setHeader('Content-Type','image/png');res.end(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAD0lEQVR4nGNgmOAAQhAKABXOA0GMr+LCAAAAAElFTkSuQmCC','base64'));return;}
 if(path.startsWith('/site/api/')){
  res.setHeader('Content-Type','application/json');
  if(req.method!=='GET'){
   let body='';for await(const chunk of req)body+=chunk;writes.push({path,method:req.method,body:JSON.parse(body)});
   if(path==='/site/api/media'){const value={media_id:'upload-'+(uploaded.length+1),island:'tenerife',url:'https://public.example/own.jpg',filename:writes.at(-1).body.filename,alt:'Photo',credit:'Owner'};uploaded.push(value);res.end(JSON.stringify(value));return;}
   res.end(JSON.stringify({...settings,draft:writes.at(-1).body.payload,version:2,status:'draft'}));return;
  }
  if(path==='/site/api/media'){res.end(JSON.stringify({items:uploaded,upload_enabled:true}));return;}
  if(path==='/site/api/analytics/passengers'){res.end(JSON.stringify({resource:'tourism',metric:'total',title:'Pasażerowie ogółem',unit:'osób',date_from:'2026-01-01',date_to:'2026-03-31',resolution:'month',aggregation:'Synthetic monthly fixture',points:[],metrics:{tourism:{total:['Pasażerowie ogółem','osób'],foreign:['Zagraniczne','osób']}},rows:[{time:'2026-01-01T12:00:00Z',value:100000,samples:1},{time:'2026-03-01T12:00:00Z',value:130000,samples:1}]}));return;}
  if(path==='/site/api/analytics/options'){res.end(JSON.stringify({points:[{resource:'weather',point_id:'santa-cruz',name:'Santa Cruz'}],metrics:{weather:{temperature:['Temperatura','°C']},'air-quality':{pm10:['PM10','µg/m³']},seismic:{magnitude:['Magnituda','']}}}));return;}
  if(path==='/site/api/analytics/series'){res.end(JSON.stringify({resource:'weather',metric:'temperature',title:'Temperatura',unit:'°C',date_from:'2026-11-01',date_to:'2026-11-03',resolution:'day',aggregation:'Synthetic fixture',rows:[{time:'2026-11-01T12:00:00Z',value:20,samples:2},{time:'2026-11-03T12:00:00Z',value:23,samples:2}]}));return;}
  if(path==='/site/api/current'){res.end(JSON.stringify({published:{name:'Aktualna treść',description:'Current body'},base_fingerprint:'0'.repeat(64)}));return;}
  if(path==='/site/api/coverage'){res.end(JSON.stringify(coverageFixture));return;}
  if(path==='/site/api/database/tables'){res.end(JSON.stringify({tables:[{name:'entities'},{name:'climate_observations'},{name:'live_snapshots'}],readonly:true}));return;}
  if(path.startsWith('/site/api/database/tables/')){const table=path.split('/').at(-1);const rows=[{id:'entity-1',canonical_name:'Tenerife',entity_type:'island'},{id:'entity-2',canonical_name:'El Hierro',entity_type:'island'}].filter(r=>!url.searchParams.get('q')||r.canonical_name.includes(url.searchParams.get('q')));res.end(JSON.stringify({table,columns:[{name:'id',type:'uuid'},{name:'canonical_name',type:'text'},{name:'entity_type',type:'text'}],rows,count:rows.length,offset:0,limit:25,readonly:true}));return;}
  if(path==='/site/api/data'){const climate=url.searchParams.get('section')==='datos';const row=climate?{observed_at:'2026-11-03T06:00:00Z',point_id:'santa-cruz',payload:{temperature:22}}:{target:'tenerife',source_updated_at:'2026-11-03T06:00:00Z',payload:{points:[{name:'Santa Cruz',temperature:23}]},status:'ok'};res.end(JSON.stringify({table:climate?'climate_observations':'live_snapshots',rows:[row],count:1,columns:Object.keys(row).map(name=>({name})),readonly:true,metrics:climate?['weather','air-quality']:[]}));return;}
  if(path.endsWith('/options')){res.end(JSON.stringify(options));return;}
  if(path.endsWith('/records')){
   const p=Object.fromEntries(url.searchParams);requests.push(p);
   if(p.kind==='settings'){res.end(JSON.stringify({items:[settings],count:1}));return;}
   const payload={name:p.island==='tenerife'?'Historia de Tenerife':'Artesanía de El Hierro',description:'Treść istniejącego artykułu z wybranej kategorii.',hidden:false};
   const item={id:null,identity:{kind:p.kind,island:p.island,resource:p.resource,record_key:'existing-fixture'},draft:payload,published:payload,status:'published',version:0,base_fingerprint:'0'.repeat(64)};
   if(p.kind==='calendar'){const items=[5,7,12].map(day=>({...item,identity:{...item.identity,record_key:'event-'+day},draft:{title:'Fiesta '+day,start_date:p.resource+'-'+String(day).padStart(2,'0'),end_date:p.resource+'-'+String(day).padStart(2,'0'),description:'Wydarzenie kalendarza',all_day:true,location:day===7?'La Laguna':'Santa Cruz',category:day===7?'Fiesta':'Cultura'},published:{title:'Fiesta '+day,description:'Wydarzenie kalendarza'}}));res.end(JSON.stringify({items,count:3}));return;}
   if(p.kind==='explore'&&p.resource==='food-producers'&&p.island==='tenerife'){res.end(JSON.stringify({items:[],count:0}));return;}
   if(p.kind==='guide'&&p.resource==='explore')item.draft=item.published={name:'Destacado de '+p.island,description:'Karta widoczna w Explore → Destacados.'};
   if(p.kind==='explore'&&p.resource==='diving-spots')item.draft=item.published={name:'Centro de Buceo',description:'Punkt nurkowy z katalogu.'};
   res.end(JSON.stringify({items:p.q?[]:[item],count:p.q?0:1}));return;
  }
  res.writeHead(404);res.end('{}');return;
 }
 const name=path==='/site/'?'index.html':path.startsWith('/site/assets/')?path.slice('/site/assets/'.length):null;
 if(!name || !['index.html','studio.js','studio.css','editorialText.js','inspector.js','charts.js'].includes(name)){res.writeHead(404);res.end();return;}
 res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css'})[extname(name)]);
 res.end(await readFile(resolve(assets,name)));
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch();
const page=await browser.newPage();await page.route('https://www.canariascerca.es/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><title>Public site preview fixture</title><p>Podgląd strony</p>'}));await page.route('https://public.example/**',r=>r.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAD0lEQVR4nGNgmOAAQhAKABXOA0GMr+LCAAAAAElFTkSuQmCC','base64')}));page.on('dialog',d=>d.accept());const errors=[];page.on('pageerror',e=>errors.push(e.message));
await mkdir('test-results/site-editor',{recursive:true});
async function idle(){await page.waitForFunction(()=>!document.querySelector('#save-settings').disabled);}
try{
 await page.goto(origin+'/site/');
 await page.locator('[data-copy="home.title"] textarea').waitFor();await idle();
 assert.equal(await page.locator('#context-title').innerText(),'Strona startowa');
 assert.equal(await page.locator('#content-view').isVisible(),false);
 assert.equal(await page.locator('[data-copy="home.title"] textarea').inputValue(),config.global.copy['home.title']);
 assert.equal(await page.locator('[data-copy="home.description"] textarea').inputValue(),options.copy_defaults['home.description']);
 assert.equal(await page.locator('[data-copy="home.description"] input').isChecked(),false);
 assert.equal(await page.locator('[data-setting]').count(),0,'visibility uses contextual switches, not select menus');
 await page.screenshot({path:'test-results/site-editor/start-settings.png',fullPage:false});
 await page.getByRole('button',{name:'Zapisz teksty i widoczność',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('Zapisano'));await idle();
 assert.deepEqual(writes[0].body.payload,config,'displaying defaults must not add or overwrite published copy');
 await page.locator('#tree-scope').selectOption('tenerife');await idle();
 assert.match(await page.locator('[data-copy="island.description"] textarea').inputValue(),/^Hola, soy Tenerife/);
 assert.equal(await page.locator('[data-copy="island.description"] input').isChecked(),false);
 await page.locator('#tree-scope').selectOption('el-hierro');await idle();
 assert.match(await page.locator('[data-copy="island.description"] textarea').inputValue(),/^Hola, soy El Hierro/);
 await page.locator('#tree-scope').selectOption('tenerife');await idle();
 await page.getByRole('button',{name:'Guía',exact:true}).click();await idle();
 await page.locator('[data-copy="nav.guide"] textarea').fill('Guía editada');
 const visibility=page.getByRole('switch');await visibility.click();
 assert.equal(await visibility.getAttribute('aria-checked'),'false');
 await page.getByRole('button',{name:'Zapisz teksty i widoczność',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('Zapisano'));await idle();
 assert.equal(writes[1].body.payload.islands.tenerife.sections.guide,false);
 assert.equal(writes[1].body.payload.islands.tenerife.copy['nav.guide'],'Guía editada','toggling visibility must preserve text entered immediately before it');
 assert.equal(Object.hasOwn(writes[1].body.payload.islands,'el-hierro'),false,'visiting an island must not add settings to the draft');
 assert.deepEqual(writes[1].body.payload.global,config.global,'island edits must preserve global text');
 await page.locator('#site-tree').getByRole('button',{name:'Historia',exact:true}).click();
 await page.locator('[data-key="description"]').waitFor();await idle();
 assert.equal(await page.locator('#island').inputValue(),'tenerife');
 assert.equal(await page.locator('#resource').inputValue(),'history');
 assert.match(await page.locator('#content-location').innerText(),/Tenerife → Guía → Conoce la isla → Historia/);
 assert.equal(await page.locator('[data-key="description"]').inputValue(),'Treść istniejącego artykułu z wybranej kategorii.','first existing article opens automatically');
 assert.match(await page.locator('#published-record-preview').innerText(),/Treść istniejącego artykułu/);
 assert.match(await page.locator('#context-visibility').innerText(),/Cała sekcja Guía jest ukryta/);
 await page.screenshot({path:'test-results/site-editor/article-workspace.png',fullPage:false});
 await page.locator('#tree-scope').selectOption('el-hierro');await idle();
 await page.getByRole('button',{name:'Artesanía',exact:true}).click();await idle();
 assert.match(await page.locator('#content-location').innerText(),/El Hierro → Guía → Cultura → Artesanía/);
 await page.locator('#search').fill('brak wyniku');
 await page.getByText('Brak wpisów dla wybranej wyspy, kategorii i wyszukiwania.',{exact:false}).waitFor();
 assert.ok(requests.some(r=>r.island==='el-hierro'&&r.resource==='crafts'));
 await page.goto(origin+'/site/?kind=guide&island=el-hierro&resource=crafts');
 await page.locator('[data-key="description"]').waitFor();await idle();
 assert.equal(await page.locator('#content-view').isVisible(),true,'AI article links retain selected content');
 assert.equal(await page.locator('#island').inputValue(),'el-hierro');
 assert.equal(await page.locator('#resource').inputValue(),'crafts');
 await page.goto(origin+'/site/?kind=news&island=canarias&resource=news');
 await page.locator('[data-key="description"]').waitFor();await idle();
 assert.equal(await page.locator('#island').inputValue(),'canarias','regional news belongs to the whole site, not arbitrarily Tenerife');
 assert.equal(await page.locator('#tree-scope').inputValue(),'global');
 await page.getByRole('switch').click();
 await page.getByRole('button',{name:'Zapisz teksty i widoczność',exact:true}).click();await idle();
 assert.equal(writes.at(-1).body.payload.global.sections.news,false,'news visibility is a section setting');
 assert.equal(Object.hasOwn(writes.at(-1).body.payload.global.features,'news.news'),false);
 await page.goto(origin+'/site/?kind=calendar&island=tenerife&resource=2026-11');
 await page.locator('[data-key="description"]').waitFor();await idle();
 assert.equal(await page.locator('#month').inputValue(),'2026-11');
 await page.getByRole('switch').click();
 await page.getByRole('button',{name:'Zapisz teksty i widoczność',exact:true}).click();await idle();
 assert.equal(writes.at(-1).body.payload.islands.tenerife.sections.calendar,false,'calendar visibility must not create invalid month feature keys');
 await page.goto(origin+'/site/');await page.locator('[data-copy="home.title"] textarea').waitFor();await idle();
 await page.locator('#site-tree').getByRole('button',{name:'Explore',exact:true}).click();await idle();
 await page.locator('#site-tree').getByRole('button',{name:'Buceo',exact:true}).click();await idle();
 await page.getByRole('button',{name:'El Hierro · 1',exact:true}).click();await idle();
 assert.equal(await page.locator('#tree-scope').inputValue(),'el-hierro');
 assert.equal(await page.locator('#editor-title').innerText(),'Centro de Buceo');
 await page.locator('#site-tree').getByRole('button',{name:'Destacados',exact:true}).click();await idle();
 assert.ok(requests.some(r=>r.kind==='guide'&&r.resource==='explore'&&r.island==='el-hierro'),'Destacados must open its real editorial source');
 assert.match(await page.locator('#editor-title').innerText(),/Destacado/);
 await page.goto(origin+'/site/?section=explore&resource=food-producers&island=tenerife');await idle();
 await page.getByText('Brak wpisów dla Tenerife. W całej bazie: 9.',{exact:true}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Fuerteventura · 6',exact:true}).count(),1,'empty island must offer actual populated islands');
 await page.locator('#site-tree').getByRole('button',{name:'Kompletność danych',exact:true}).click();await idle();
 assert.match(await page.locator('#inspection-view').innerText(),/Bodegas y queserías/);
 await page.locator('#site-tree').getByRole('button',{name:'Live',exact:true}).click();await idle();
 assert.match(await page.locator('#inspection-view').innerText(),/Santa Cruz/);
 await page.locator('#site-tree').getByRole('button',{name:'Datos',exact:true}).click();await idle();
 assert.match(await page.locator('#inspection-view').innerText(),/climate_observations/);
 await page.locator('.chart-plot svg').waitFor();
 assert.equal(await page.getByLabel('Miasto lub punkt pomiarowy').inputValue(),'santa-cruz');
 await page.locator('#inspection-view').screenshot({path:'test-results/site-editor/climate-chart.png'});
 await page.locator('#site-tree').getByRole('button',{name:'Turismo',exact:true}).click();await idle();await page.getByRole('img',{name:/Pasażerowie ogółem/}).waitFor();assert.equal(await page.getByLabel('Rozdzielczość wykresu').inputValue(),'month');
 await page.locator('#site-tree').getByRole('button',{name:'Baza danych',exact:true}).click();await idle();
 await page.getByLabel('Tabela bazy danych').selectOption('entities');
 await page.getByLabel('Szukaj w tabeli').fill('Tenerife');
 await page.waitForFunction(()=>document.querySelector('#inspection-view').innerText.includes('1 rekordów'));
 assert.match(await page.locator('#inspection-view').innerText(),/Tenerife/);
 await page.screenshot({path:'test-results/site-editor/database-browser.png',fullPage:false});
 await page.goto(origin+'/site/?kind=calendar&island=tenerife&resource=2026-11');
 await page.getByRole('button',{name:'Fiesta 7',exact:true}).waitFor();await idle();
 assert.equal(await page.locator('.calendar-day').count(),42);
 await page.locator('#calendar-town').selectOption('La Laguna');await idle();
 assert.equal(await page.locator('.calendar-event').count(),1);
 await page.getByRole('button',{name:'Fiesta 7',exact:true}).click();
 assert.equal(await page.locator('#editor-title').innerText(),'Fiesta 7');
 await page.getByRole('button',{name:'Historia wersji treści',exact:true}).click();
 await page.getByRole('dialog').waitFor();assert.match(await page.locator('#history-dialog-content').innerText(),/nie był jeszcze edytowany/);await page.locator('#close-history').click();
 await page.locator('#rebase').click();await page.locator('#preview-dialog[open]').waitFor();await page.locator('#close-preview').click();
 await page.locator('#site-tree').getByRole('button',{name:'Transporte',exact:true}).click();await idle();assert.equal(await page.locator('#site-tree').getByRole('button',{name:'Aeropuertos',exact:true}).count(),1);
 await page.locator('#inspection-view').screenshot({path:'test-results/site-editor/transport.png'});
 await page.goto(origin);
 await page.waitForFunction(()=>document.querySelector('#api-status').textContent==='Edytor · połączony');
 await page.frameLocator('#site-editor-frame').locator('[data-copy="home.title"] textarea').waitFor();
 await page.screenshot({path:'test-results/site-editor/unified-editor.png',fullPage:false});
 await page.getByRole('button',{name:'Podgląd strony',exact:true}).click();
 await page.getByRole('button',{name:'Telefon',exact:true}).click();
 assert.equal(await page.locator('#website-preview-frame').evaluate(e=>e.getBoundingClientRect().width),390);
 assert.equal(await page.getByRole('button',{name:'LangGraph',exact:true}).count(),0);
 await page.goto(origin+'/site/?section=live&resource=weather&island=tenerife');await idle();assert.equal(await page.locator('#site-tree').getByRole('button',{name:'Własne punkty Live',exact:true}).count(),0);await page.getByRole('button',{name:'Dodaj punkt',exact:true}).click();await idle();assert.equal(await page.locator('#kind').inputValue(),'live-point');assert.equal(await page.locator('[data-key="latitude"]').count(),1);
 optionalHealthFailure=false;await page.goto(origin);await page.waitForFunction(()=>document.querySelector('#api-status').textContent==='Edytor · połączony');
 await page.getByRole('button',{name:'Wydarzenia',exact:true}).click();await page.locator('#new-manual-event').click();
 const editor=page.frameLocator('#site-editor-frame');await editor.getByRole('heading',{name:'Nowe wydarzenie',exact:true}).waitFor();assert.equal(await editor.locator('#island').inputValue(),'tenerife');assert.equal(await editor.locator('#kind').inputValue(),'calendar');
 await page.goto(origin);await page.frameLocator('#site-editor-frame').locator('#tree-scope').selectOption('tenerife');await page.frameLocator('#site-editor-frame').getByRole('button',{name:'Guía',exact:true}).click();await page.frameLocator('#site-editor-frame').getByRole('button',{name:'Historia',exact:true}).click();await page.frameLocator('#site-editor-frame').locator('[data-key="description"]').waitFor();
 await page.frameLocator('#site-editor-frame').getByRole('button',{name:'Wybierz zdjęcie z biblioteki',exact:true}).click();await page.locator('#photo-gallery').getByRole('button',{name:/Teide.jpg/}).waitFor();assert.match(await page.locator('#photo-folder-tree').innerText(),/volcanoes/);assert.equal(await page.locator('#photo-library-frame').count(),0,'one photo library, no duplicate iframe');
 await page.locator('#photo-upload-file').setInputFiles({name:'own.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAD0lEQVR4nGNgmOAAQhAKABXOA0GMr+LCAAAAAElFTkSuQmCC','base64')});await page.waitForFunction(()=>document.querySelector('#photo-preview-title').textContent==='own.jpg');assert.equal(uploaded.length,1);assert.match(writes.at(-1).body.data,/^\/9j\//,'phone photo is JPEG before durable upload');
 await page.locator('#view-photos').screenshot({path:'test-results/site-editor/unified-photo-library.png'});await page.locator('#photo-use').click();await page.frameLocator('#site-editor-frame').locator('[data-key="image_url"]').waitFor();assert.equal(await page.frameLocator('#site-editor-frame').locator('[data-key="image_url"]').inputValue(),'https://public.example/own.jpg');
 await page.frameLocator('#site-editor-frame').locator('#improve-ai').click();await page.waitForFunction(()=>document.querySelector('#topic').value==='Historia de Tenerife');
 assert.deepEqual(errors,[],'editor must boot and switch views without JS failures');
 assert.ok(writes.every(r=>['/site/api/draft','/site/api/media'].includes(r.path)),'UI test never publishes');
 console.log('EDITOR UI PASS: site tree, real text, automatic article selection, contextual switches, inheritance, draft preservation, empty state and direct links.');
}finally{await browser.close();server.close();}
