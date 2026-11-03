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
const requests=[],writes=[];
const options={islands:['el-hierro','la-palma','la-gomera','tenerife','gran-canaria','fuerteventura','lanzarote','la-graciosa'],sections:{explore:'Explore',live:'Live',calendar:'Calendario',news:'Noticias',datos:'Datos',guide:'Guía'},features:{guide:['crafts','culture','history','food','geology','nature'],explore:['places','beaches'],datos:['climate']},copy_defaults:{'home.title':'Hola, somos las Islas Canarias.','home.description':'Ocho islas, miles de lugares por descubrir.','island.description':'','nav.guide':'Guía',...defaults}};
const server=createServer(async(req,res)=>{
 const url=new URL(req.url,'http://localhost');const path=url.pathname;
 if(path==='/health/ready'){res.setHeader('Content-Type','application/json');res.end('{"status":"ok"}');return;}
 if(path==='/health'){res.writeHead(500,{'Content-Type':'application/json'});res.end('{"detail":"optional configuration unavailable"}');return;}
 if(path==='/api/v1/content'){res.setHeader('Content-Type','application/json');res.end('[]');return;}
 if(path==='/' || path.startsWith('/static/')){
  const name=path==='/'?'index.html':path.slice('/static/'.length);
  if(!['index.html','styles.css','app.js','studio-extras.js'].includes(name)){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css'})[extname(name)]);res.end(await readFile(resolve(staticAssets,name)));return;
 }
 if(path.startsWith('/site/api/')){
  res.setHeader('Content-Type','application/json');
  if(req.method!=='GET'){
   let body='';for await(const chunk of req)body+=chunk;writes.push({path,method:req.method,body:JSON.parse(body)});
   res.end(JSON.stringify({...settings,draft:writes.at(-1).body.payload,version:2,status:'draft'}));return;
  }
  if(path.endsWith('/options')){res.end(JSON.stringify(options));return;}
  if(path.endsWith('/records')){
   const p=Object.fromEntries(url.searchParams);requests.push(p);
   if(p.kind==='settings'){res.end(JSON.stringify({items:[settings],count:1}));return;}
   const payload={name:p.island==='tenerife'?'Historia de Tenerife':'Artesanía de El Hierro',description:'Treść istniejącego artykułu z wybranej kategorii.',hidden:false};
   const item={id:null,identity:{kind:p.kind,island:p.island,resource:p.resource,record_key:'existing-fixture'},draft:payload,published:payload,status:'published',version:0,base_fingerprint:'0'.repeat(64)};
   res.end(JSON.stringify({items:p.q?[]:[item],count:p.q?0:1}));return;
  }
  res.writeHead(404);res.end('{}');return;
 }
 const name=path==='/site/'?'index.html':path.startsWith('/site/assets/')?path.slice('/site/assets/'.length):null;
 if(!name || !['index.html','studio.js','studio.css','editorialText.js'].includes(name)){res.writeHead(404);res.end();return;}
 res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.css':'text/css'})[extname(name)]);
 res.end(await readFile(resolve(assets,name)));
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const origin=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch();
const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
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
 const visibility=page.getByRole('switch');await visibility.click();
 assert.equal(await visibility.getAttribute('aria-checked'),'false');
 await page.getByRole('button',{name:'Zapisz teksty i widoczność',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('Zapisano'));await idle();
 assert.equal(writes[1].body.payload.islands.tenerife.sections.guide,false);
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
 await page.goto(origin);
 await page.waitForFunction(()=>document.querySelector('#api-status').textContent==='Edytor · połączony');
 await page.frameLocator('#site-editor-frame').locator('[data-copy="home.title"] textarea').waitFor();
 await page.screenshot({path:'test-results/site-editor/unified-editor.png',fullPage:false});
 assert.deepEqual(errors,[],'editor must boot and switch views without JS failures');
 assert.ok(writes.every(r=>r.path==='/site/api/draft'),'UI test never publishes');
 console.log('EDITOR UI PASS: site tree, real text, automatic article selection, contextual switches, inheritance, draft preservation, empty state and direct links.');
}finally{await browser.close();server.close();}
