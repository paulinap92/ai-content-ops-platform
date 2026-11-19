// Real Lugares assets; isolated API fixtures only. No hosted traffic.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {chromium} from 'playwright';
const assets=new URL('../canarias_site/studio/',import.meta.url);
const row={entity_id:'11111111-1111-4111-8111-111111111111',name:'Lugar <img src=x onerror=alert(1)>',island:'tenerife',cc_revision:1,short_description:'Descripción comprobada.',body:'Primera frase. Segunda frase.',cc_sources:[{url:'https://example.org/source',title:'Institutional source',http_status:200,checked_at:'2026-11-18T12:00:00Z'}],fingerprint:'a'.repeat(64),cc_review_status:'draft',cc_verification_status:'verified',publication_status:'draft',publish_enabled:false};
let current={...row}, writes=[];
const server=createServer(async(req,res)=>{
 const u=new URL(req.url,'http://localhost');res.setHeader('Content-Type','application/json');
 if(u.pathname==='/site/lugares'){res.setHeader('Content-Type','text/html');res.end(await readFile(new URL('lugares.html',assets)));return;}
 if(u.pathname.startsWith('/site/assets/')){const name=u.pathname.split('/').at(-1);if(!['lugares.js','studio.css'].includes(name)){res.writeHead(404);res.end();return;}res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':'text/css');res.end(await readFile(new URL(name,assets)));return;}
 if(req.method==='GET'){res.end(JSON.stringify({items:[current],total:1}));return;}
 let raw='';for await(const chunk of req)raw+=chunk;const body=JSON.parse(raw);writes.push(body);
 if(req.method==='PUT')current={...current,...body,body:body.detailed_description,cc_sources:body.sources,cc_revision:current.cc_revision+1,cc_verification_status:'needs_review',cc_review_status:'draft',fingerprint:'b'.repeat(64)};
 else if(body.action==='verify')current={...current,cc_verification_status:'verified',fingerprint:'c'.repeat(64)};
 else if(body.action==='approve')current={...current,cc_review_status:'approved',fingerprint:'d'.repeat(64)};
 res.end(JSON.stringify(current));
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch(process.env.CC_TEST_CHROMIUM ? {executablePath:process.env.CC_TEST_CHROMIUM} : {});const page=await browser.newPage();
try{
 await page.goto(`http://127.0.0.1:${server.address().port}/site/lugares`);
 await page.waitForFunction(()=>!document.getElementById('editor').hidden);
 assert.equal(await page.locator('#title img').count(),0);
 assert.equal(await page.locator('#island option').count(),9);
 assert.equal(await page.locator('#publish').isDisabled(),true);
 await page.locator('#actor').fill('Isolated editor');
 await page.locator('#short').fill('Nuevo texto comprobado.');
 assert.equal(await page.locator('#approve').isDisabled(),true);
 await page.locator('#save').click();await page.waitForFunction(()=>document.getElementById('identity').textContent.includes('rewizja 2'));
 assert.equal(writes[0].expected_fingerprint,'a'.repeat(64));
 assert.equal(writes[0].sources[0].url,'https://example.org/source');
 for(const id of ['facts','links','sentences'])await page.locator('#'+id).check();
 await page.locator('#verify').click();await page.waitForFunction(()=>document.getElementById('status').textContent.startsWith('zweryfikowany'));
 await page.locator('#style').check();await page.locator('#approve').click();await page.waitForFunction(()=>document.getElementById('status').textContent.includes('zatwierdzony'));
 assert.equal(writes.at(-1).action,'approve');assert.equal(await page.locator('#publish').isDisabled(),true);
 await page.locator('#history-button').click();await page.locator('#history summary').waitFor();
 assert.equal(await page.locator('#history img').count(),0);
 console.log('PASS Lugares: search/islands, XSS escaping, new revision, source form, verify, approve, publication disabled, history');
}finally{await browser.close();await new Promise(r=>server.close(r));}
