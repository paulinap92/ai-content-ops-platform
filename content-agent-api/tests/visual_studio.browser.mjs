import assert from 'node:assert/strict';
import {readFile,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve,extname} from 'node:path';
import {chromium} from 'playwright';
const assets=fileURLToPath(new URL('../canarias_site/studio/',import.meta.url));
const EDITOR='https://canarias-content-editor.onrender.com',SITE='https://www.canariascerca.es',key='de821d68-e82c-4501-a291-123456789abc';
const identity={kind:'explore',island:'tenerife',resource:'places',record_key:key};
const payload={name:'Existing place',short_description:'Existing short.',detailed_description:'Existing details.',description:'Existing short.',category:'museum',latitude:28.2,longitude:-16.5,sources:[{url:'https://example.com/source',title:'Official'}],gallery:[]};
let item={id:null,identity,version:0,status:'published',draft:payload,published:payload,base_fingerprint:'0'.repeat(64)};
const config={global:{sections:{},features:{},copy:{}},islands:{}},settings={id:'settings',identity:{kind:'settings',island:'global',resource:'site',record_key:'site'},draft:config,published:config,version:1,status:'published',base_fingerprint:'0'.repeat(64)};
const errors=[],uploads=[];
const manifest={schema_version:1,generated_from:'js/core/routes.js',routes:[{path:'/',island:null,section:null,resource:null,title:'Home',mode:'presentation'}, {path:'/tenerife/explore/lugares/',island:'tenerife',section:'explore',resource:'places',title:'Lugares',mode:'editorial',api:'/api/regions/canarias/places',source:'design.entity_source_properties',editor:{kind:'explore',resource:'places'}}]};
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAD0lEQVR4nGNgmOAAQhAKABXOA0GMr+LCAAAAAElFTkSuQmCC','base64');
const browser=await chromium.launch(process.env.CC_TEST_CHROMIUM?{executablePath:process.env.CC_TEST_CHROMIUM}:{}),page=await browser.newPage({viewport:{width:1600,height:1000}});
page.setDefaultTimeout(8000);
page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
await page.route('**/*',async route=>{
 const request=route.request(),u=new URL(request.url()),json=v=>route.fulfill({contentType:'application/json',body:JSON.stringify(v)});
 if(u.origin===SITE)return route.fulfill({contentType:'text/html',body:`<!doctype html><button id="choose">Existing place</button><p id="draft"></p><script>const origin='${EDITOR}';choose.onclick=()=>parent.postMessage({type:'cc-studio-select',route:{valid:true,island:'tenerife',section:'explore',resource:'places'},selection:{kind:'explore',resource:'places',record_key:'${key}'}},origin);window.addEventListener('message',e=>{if(e.origin===origin&&e.data.type==='cc-studio-draft')draft.textContent=e.data.payload.short_description;});parent.postMessage({type:'cc-studio-ready',route:{valid:true,island:null,section:null,resource:null}},origin);</script>`});
 if(u.hostname==='public.example')return route.fulfill({contentType:'image/png',body:png});
 if(u.origin!==EDITOR)return route.abort();
 const path=u.pathname;
 if(path==='/site/')return route.fulfill({contentType:'text/html',body:await readFile(resolve(assets,'index.html'))});
 if(path.startsWith('/site/assets/')){const name=path.split('/').at(-1);return route.fulfill({contentType:({'.css':'text/css','.png':'image/png','.jpg':'image/jpeg'})[extname(name)]||'text/javascript',body:await readFile(resolve(assets,name))});}
 if(request.method()!=='GET'){
  const body=request.postDataJSON();
 if(path==='/site/api/media'){const image={url:'https://public.example/image.png',filename:'Own image',alt:body.alt||'',credit:body.credit||'',media_id:'one',island:'tenerife'};uploads.push(image);return json(image);}
  if(path==='/site/api/draft'){item={...item,id:'document',draft:body.payload,version:item.version+1,status:'draft'};return json(item);}
  if(path.endsWith('/publish')){assert.equal(body.review_confirmed,true);item={...item,published:item.draft,version:item.version+1,status:'published'};return json(item);}
  throw Error('Unexpected mutation '+path);
 }
  if(path==='/site/api/database/tables')return json({tables:[{name:'entities'}]});
 if(path==='/site/api/database/tables/entities')return json({table:'entities',count:1,columns:[{name:'id',type:'uuid'},{name:'canonical_name',type:'text'}],rows:[{id:key,canonical_name:'Real database row'}]});
 if(path==='/site/api/options')return json({islands:['tenerife'],sections:{explore:'Explore',guide:'Guía',live:'Live',calendar:'Calendario',news:'Noticias',datos:'Datos'},features:{explore:['places','beaches'],guide:['history'],live:['weather'],datos:['climate']},copy_defaults:{'home.title':'Home','home.description':'Description'},media_upload_enabled:true});
 if(path==='/site/api/coverage')return json({guide:{history:{total:1,islands:{tenerife:1}}},islands:['tenerife'],explore:{},calendar:[],live:[],climate:[],statistics:[],notes:'Fixture'});
 if(path==='/site/api/site-manifest')return json(manifest);
 if(path==='/site/api/records')return json(u.searchParams.get('kind')==='settings'?{items:[settings],count:1}:{items:[item],count:1});
 if(path==='/site/api/open-record')return json(item);
 if(path==='/site/api/lugares-catalog')return json({published:372,blocked:8,overlay_rows:403,items:[{name:'Existing place',canonical_id:key,island:'tenerife',resource:'places',state:'published'}]});
 if(path==='/site/api/media')return json({items:uploads,upload_enabled:true});
 if(path==='/site/api/media/file')return route.fulfill({contentType:'image/png',body:png});
 if(path==='/api/v1/photos')return json([]);
 return route.fulfill({status:404,contentType:'application/json',body:'{}'});
});
try{
 await page.goto(EDITOR+'/site/');await page.locator('#visual-frame').waitFor();
 await page.frameLocator('#visual-frame').locator('#choose').click();await page.locator('[data-key="short_description"]').waitFor();
 assert.equal(await page.locator('[data-key="detailed_description"]').inputValue(),'Existing details.');
 await page.locator('#generate-social-graphic').click();
 assert.equal(await page.locator('#tpl-title').inputValue(),'Existing place');
 assert.equal(await page.locator('#tpl-type').inputValue(),'lugares');
 await page.waitForFunction(()=>!document.querySelector('#tpl-save').disabled);
 for(const type of ['noticias','eventos','lugares','datos','guia']){
  await page.locator('#tpl-type').selectOption(type);
  for(const style of ['oficial','ai']){
   await page.locator('#tpl-style').selectOption(style);
   for(const [format,width,height] of [['ig',1080,1350],['fb',1200,630],['wa',1080,1080],['story',1080,1920]]){
    await page.locator('#tpl-format').selectOption(format);
    const dims=await page.locator('#tpl-canvas').evaluate(c=>[c.width,c.height,c.toDataURL('image/png').startsWith('data:image/png;base64,')]);
    assert.deepEqual(dims,[width,height,true]);
   }
  }
 }
 await page.locator('#tpl-title').fill('Un título largo para conocer todos los lugares increíbles de las Islas Canarias durante el próximo fin de semana');
 await page.locator('#tpl-detail').fill('Una descripción extensa con información útil, fechas, horarios, recomendaciones y detalles para preparar la visita.');
 await page.locator('#tpl-photo').setInputFiles({name:'test.png',mimeType:'image/png',buffer:png});
 await page.waitForFunction(()=>!document.querySelector('#tpl-library').disabled);
 assert.equal(uploads.length,0,'Opening templates must not persist or publish anything');
 await page.locator('#tpl-back').click();
 assert.equal(await page.locator('[data-key="detailed_description"]').inputValue(),'Existing details.');
 await page.locator('[data-key="short_description"]').fill('A new short description.');await page.locator('[data-key="detailed_description"]').fill('A new detailed description.');
 await page.getByRole('button',{name:'Zdjęcia i galeria',exact:true}).click();
 await page.locator('.record-photo input[type=file]').setInputFiles({name:'own.png',mimeType:'image/png',buffer:png});
 await page.waitForFunction(()=>document.querySelector('[data-key=image_url]').value==='https://public.example/image.png');
 await page.locator('[data-key=image_alt]').fill('A photograph of the place');
 await page.locator('#record-gallery').getByRole('button',{name:'+ Dodaj zdjęcie z biblioteki',exact:true}).click();await page.locator('dialog').getByRole('button',{name:'Own image'}).click();
 assert.equal(await page.locator('.gallery-row').count(),1);
 await page.locator('#record-gallery input[type=file]').setInputFiles({name:'gallery.png',mimeType:'image/png',buffer:png});
 await page.waitForFunction(()=>document.querySelectorAll('.gallery-row').length===2);

 await page.locator('#visual-draft').click();await page.frameLocator('#visual-frame').locator('#draft').filter({hasText:'A new short description.'}).waitFor();assert.equal(await page.frameLocator('#visual-frame').locator('#draft').textContent(),'A new short description.');
 await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#record-status').textContent.includes('wersja 1'));
 assert.equal(item.published.short_description,'Existing short.','Saving a draft preserves the live copy');
 await page.locator('#publication-review').check();await page.locator('#publish').click();await page.waitForFunction(()=>document.querySelector('#record-status').textContent.includes('wersja 2'));
 assert.equal(item.published.short_description,'A new short description.');assert.equal(item.published.gallery.length,2);
 await mkdir('test-results/site-editor',{recursive:true});await page.screenshot({path:'test-results/site-editor/compact-photos.png',fullPage:true});
 await page.getByRole('button',{name:'Treść',exact:true}).click();
 await page.locator('[data-key=hidden]').uncheck();
 await page.getByRole('button',{name:'Linki i źródła',exact:true}).click();await page.locator('[data-key=show_links]').uncheck();
 await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#record-status').textContent.includes('wersja 3'));
 assert.equal(item.draft.hidden,true);assert.equal(item.draft.show_links,false);
 assert.notEqual(item.published.hidden,true,'visibility is not changed on the public site until publication');
 await page.locator('#publication-review').check();await page.locator('#publish').click();await page.waitForFunction(()=>document.querySelector('#record-status').textContent.includes('wersja 4'));
 assert.equal(item.published.hidden,true);assert.equal(item.published.show_links,false);
 await page.locator('#open-release').click();await page.locator('#manifest-source').filter({hasText:'372 opisy'}).waitFor();assert.match(await page.locator('#manifest-source').textContent(),/372.*8.*403/);
 await page.getByRole('button',{name:'Treść',exact:true}).click();
 item={...item,blocked_reason:'Identity needs review'};await page.locator('#visual-tree button').filter({hasText:'Existing place'}).click();
 await page.locator('.release-blocked').waitFor();assert.equal(await page.locator('#publish').isDisabled(),true);
 await page.locator('#open-database').click();await page.getByText('Real database row',{exact:true}).waitFor();
 assert.equal(await page.locator('#visual-preview').isVisible(),false,'Database view must not show the website preview');
 assert.equal(await page.locator('#visual-frame').isVisible(),false);
 await page.goto(EDITOR+'/site/?view=guide');
 await page.getByText('Guía · wybierz kategorię i wyspę',{exact:true}).waitFor();
 assert.equal(await page.locator('#open-articles').getAttribute('aria-current'),'page');
 await page.getByRole('button',{name:'Tenerife · 1',exact:true}).click();
 await page.locator('#editor-title').waitFor();
 await page.goto(EDITOR+'/site/?view=database');await page.getByText('Real database row',{exact:true}).waitFor();
 assert.equal(await page.locator('#visual-preview').isVisible(),false,'Direct database navigation must stay in the table browser');
 await page.locator('#open-lugares').click();await page.locator('#site-tree').getByRole('button',{name:'Playas',exact:true}).click();
 await page.locator('#catalog-new').click();await page.getByRole('heading',{name:'Nowe miejsce',exact:true}).waitFor();
 assert.equal(await page.locator('#resource').inputValue(),'beaches');assert.equal(await page.locator('#publish').isDisabled(),true,'new points must be saved before publishing');
 await page.getByRole('button',{name:'Położenie / pinezka',exact:true}).click();
 assert.equal(await page.locator('[data-key=latitude]').isVisible(),true);assert.equal(await page.locator('[data-key=longitude]').isVisible(),true);
 assert.equal(await page.locator('.map-location iframe').count(),0,'new points must not show a false marker at zero coordinates');
 await page.locator('[data-key=latitude]').fill('28.2');await page.locator('[data-key=longitude]').fill('-16.5');await page.getByRole('button',{name:'Odśwież położenie na mapie',exact:true}).click();
 assert.match(await page.locator('.map-location iframe').getAttribute('src'),/28.2/);
 await page.getByRole('button',{name:'Treść',exact:true}).click();
 await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'the editor fits a phone');
 await mkdir('test-results/site-editor',{recursive:true});await page.screenshot({path:'test-results/site-editor/universal-studio.png',fullPage:true});assert.deepEqual(errors,[]);
 console.log('VISUAL STUDIO UI PASS: selection, upload, gallery, draft preview, save, publication and blocked catalogue');
}catch(e){await mkdir('test-results/site-editor',{recursive:true});await page.screenshot({path:'test-results/site-editor/failed.png',fullPage:true});console.error({errors,status:await page.locator('#status').textContent()});throw e;}finally{await browser.close();}
