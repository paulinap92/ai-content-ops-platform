import assert from 'node:assert/strict';
import {readFile,mkdir} from 'node:fs/promises';
import {resolve,extname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
const root=fileURLToPath(new URL('../',import.meta.url)),frontend=fileURLToPath(new URL('../../../frontend/',import.meta.url));
const EDITOR='https://canarias-content-editor.onrender.com',SITE='https://www.canariascerca.es';
let source={id:'source',name:'Existing official source',url:'https://example.com/feed',island:'tenerife',active:true,version:0},record=null,publicNews=[],job=null;
const errors=[],writes=[];
const settings={id:'settings',identity:{kind:'settings',island:'global',resource:'site',record_key:'site'},version:1,status:'published',draft:{global:{sections:{},features:{},copy:{}},islands:{}},published:null,base_fingerprint:'0'.repeat(64)};
const browser=await chromium.launch(process.env.CC_TEST_CHROMIUM?{executablePath:process.env.CC_TEST_CHROMIUM}:{}),page=await browser.newPage({viewport:{width:1280,height:900}});page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
await page.route('**/*',async route=>{
 const req=route.request(),u=new URL(req.url()),path=u.pathname,json=value=>route.fulfill({contentType:'application/json',body:JSON.stringify(value)});
 if(u.origin===SITE){if(path.startsWith('/js/'))return route.fulfill({contentType:'text/javascript',body:await readFile(resolve(frontend,path.slice(1)))});if(path.startsWith('/api/'))return json(publicNews.filter(item=>!u.searchParams.get('article')||item.id===u.searchParams.get('article')));return route.fulfill({contentType:'text/html',body:'<!doctype html><main id="news"></main><script type="module">import {renderNews} from "/js/guide/news.js";const article=new URLSearchParams(location.search).get("articulo");const data=await fetch("/api/news"+(article?"?article="+encodeURIComponent(article):"")).then(r=>r.json());news.innerHTML=renderNews(data);</script>'});}
 if(u.origin!==EDITOR)return route.abort();
 if(path==='/'||path==='/site/')return route.fulfill({contentType:'text/html',body:await readFile(resolve(root,path==='/site/'?'canarias_site/studio/index.html':'static/index.html'))});
 if(path.startsWith('/static/')||path.startsWith('/site/assets/'))return route.fulfill({contentType:path.endsWith('.css')?'text/css':'text/javascript',body:await readFile(resolve(root,path.startsWith('/static/')?'static/'+path.split('/').at(-1):'canarias_site/studio/'+path.split('/').at(-1)))});
 if(path==='/health')return json({photo_source:'drive',ai_configured:true,canarias_publish_enabled:true,content_languages:['es']});
 if(path==='/health/ready')return json({status:'ok'});
 if(req.method()!=='GET'){
  const body=req.postDataJSON();writes.push({path,body});
  if(path==='/site/api/noticias/sources'){source={...source,...body,version:source.version+1};return json(source);}
  if(path==='/site/api/noticias/discover')return json({items:[{title:'Una noticia <img src=x onerror=alert(1)>',source_url:'https://example.com/story',excerpt:'Source material for a new article.'}]});
  if(path==='/site/api/noticias/extract')return json({title:'Imported title',source_url:body.url,material:'Additional source material. This is not a published article.'});
  if(path==='/site/api/noticias/draft'){record={id:'news-document',identity:{kind:'news',island:body.island,resource:'news',record_key:'new:noticias-one'},draft:{title:body.title,description:body.description,summary:body.summary,category:body.category,topics:[body.category],source_url:body.source_url,url:'',hidden:false,show_links:true},published:null,status:'draft',version:1,base_fingerprint:'0'.repeat(64)};return json({record,existing:false});}
  if(path==='/site/api/draft'){record={...record,draft:body.payload,version:record.version+1};return json(record);}
  if(path==='/site/api/documents/news-document/publish'){record={...record,identity:{...record.identity,record_key:'manual:one'},published:{...record.draft,id:'manual:one',editorial_override:true},status:'published',version:record.version+1};publicNews=[record.published];return json(record);}
  if(path==='/api/v1/content'){job={...body,thread_id:'job-news',status:'awaiting_review',revision_count:0,outline:'Propozycja do sprawdzenia',site_target:body.site_target};return json({thread_id:'job-news',status:'researching'});}
  throw Error('Unexpected mutation '+path);
 }
 if(path==='/site/api/noticias/options')return json({islands:{canarias:'Całe Kanary',tenerife:'Tenerife'},categories:{other:'Inne',science:'Nauka'},ai_enabled:true,search_enabled:true});
 if(path==='/site/api/noticias/sources')return json({items:[source]});
 if(path==='/site/api/noticias/queue')return json({items:record?[record]:[],count:record?1:0});
 if(path==='/api/v1/content')return json([]);
 if(path==='/api/v1/content/job-news')return json(job);
 if(path==='/site/api/options')return json({islands:['tenerife'],sections:{explore:'Explore',guide:'Guía',calendar:'Calendario',news:'Noticias'},features:{explore:['places'],guide:['history']},copy_defaults:{},media_upload_enabled:true});
 if(path==='/site/api/records')return json({items:u.searchParams.get('kind')==='settings'?[settings]:record?[record]:[],count:1});
 if(path==='/site/api/site-manifest')return json({generated_from:'js/core/routes.js',routes:[]});
 if(path.startsWith('/api/v1/photos'))return json([]);
 return route.fulfill({status:404,contentType:'application/json',body:'{}'});
});
try{
 await page.goto(EDITOR+'/?view=noticias');await page.getByText('Wybierz materiał albo napisz własną wiadomość.',{exact:true}).waitFor();
 await page.locator('#noticias-island').selectOption('tenerife');await page.locator('#noticias-discover').click();
 await page.getByRole('button',{name:'Przygotuj wiadomość na podstawie materiału'}).waitFor();
 assert.equal(await page.locator('#noticias-results img').count(),0,'source titles enter the DOM as text');
 await page.getByRole('button',{name:'Przygotuj wiadomość na podstawie materiału'}).click();
 assert.equal(await page.locator('#noticias-body').inputValue(),'','discovery never copies source text to the public article');
 await page.locator('#noticias-title').fill('Una noticia propia');await page.locator('#noticias-category').selectOption('science');
 await page.locator('#noticias-extract').click();await page.locator('#noticias-material').filter({visible:true}).waitFor();
 await page.waitForFunction(()=>document.querySelector('#noticias-material').value.includes('Additional source'));
 await page.locator('#noticias-summary').fill('Resumen propio.');await page.locator('#noticias-body').fill('## Información\n\nEl texto completo de la noticia, redactado por nosotros.');
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Noticias desk fits a phone');
 await mkdir('test-results/site-editor',{recursive:true});await page.screenshot({path:'test-results/site-editor/noticias-phone.png',fullPage:true});
 await page.locator('#noticias-save').click();await page.locator('[data-key=description]').waitFor();
 assert.equal(record.identity.kind,'news');assert.equal(record.identity.island,'tenerife');assert.equal(record.draft.category,'science');
 assert.equal(publicNews.length,0,'staging leaves the public site untouched');
 assert.equal(writes.filter(w=>w.path.includes('/publish')).length,0);
 await page.locator('#publish').click();await page.waitForFunction(()=>document.querySelector('#record-status').textContent.includes('wersja 2'));
 assert.equal(publicNews.length,1);
 await page.goto(SITE+'/tenerife/noticias/?articulo=manual%3Aone');await page.locator('.news-full-article[open]').waitFor();
 assert.match(await page.locator('.news-full-article').innerText(),/El texto completo de la noticia/);
 assert.equal(await page.locator('.news-card').getAttribute('data-news-topics'),'science');
 assert.match(await page.getByRole('link',{name:'Enlace a este artículo ↗'}).getAttribute('href'),/articulo=manual%3Aone/);
 await page.goto(EDITOR+'/?view=noticias');await page.locator('#noticias-queue-list').getByRole('button',{name:/Una noticia propia/}).waitFor();
 await page.locator('#noticias-new').click();await page.locator('#noticias-title').fill('Una noticia con AI');await page.locator('#noticias-body').fill('Material para preparar y revisar.');
 await page.locator('#noticias-ai').click();await page.getByText('Propozycja do sprawdzenia',{exact:true}).waitFor();
 assert.equal(job.content_type_hint,'news');assert.equal(job.site_target.identity.kind,'news');assert.equal(job.site_target.identity.resource,'news');
 assert.equal(writes.filter(w=>w.path.includes('/publish')).length,1,'AI preparation never publishes');
 assert.deepEqual(errors,[]);console.log('NOTICIAS DESK UI PASS: discovery, source material, original text, category, phone layout, private draft, publication, full public article, permalink and AI news target');
}catch(e){console.error({errors,body:(await page.locator('body').innerText()).slice(0,1500)});throw e;}finally{await browser.close();}
