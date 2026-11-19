const $ = id => document.getElementById(id);
let current = null, offset = 0, total = 0, dirty = false;
const labels = {draft:'szkic', approved:'zatwierdzony', published:'opublikowany', verified:'zweryfikowany', needs_review:'wymaga kontroli', unchecked:'niesprawdzony'};
const node = (tag, text) => { const e=document.createElement(tag); if(text!==undefined)e.textContent=text; return e; };
async function api(path, method='GET', body) {
  const r = await fetch('/site/api/lugares'+path,{method, headers:{'Content-Type':'application/json'}, ...(body?{body:JSON.stringify(body)}:{})});
  if(r.status===401){location.assign('/login');throw Error('Zaloguj się ponownie.');}
  const data=await r.json(); if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Sprawdź pola formularza.'); return data;
}
async function task(fn){try{await fn();}catch(e){$('message').textContent=e.message;}}
function sourceRow(source={url:'',title:''}){
  const box=node('fieldset');box.className='lugares-source';
  for(const [key,label] of [['title','Nazwa źródła'],['url','Adres HTTPS']]){
    const l=node('label',label),input=node('input');input.dataset.field=key;input.value=source[key]||'';input.required=true;input.maxLength=key==='url'?2048:500; if(key==='url')input.type='url'; l.append(input);box.append(l);
  }
  const a=node('a','Otwórz źródło ↗');a.target='_blank';a.rel='noopener noreferrer';
  const update=()=>{try{const u=new URL(box.querySelector('[data-field="url"]').value);if(u.protocol!=='https:'||u.username||u.password)throw Error();a.href=u.href;a.hidden=false;}catch{a.removeAttribute('href');a.hidden=true;}};
  update();box.addEventListener('input',update);box.append(a,node('p',source.checked_at?`Kontrola: ${source.checked_at} · ${source.check_method==='authenticated_editor_attestation'?'potwierdzenie redaktora':source.http_status||'brak wyniku'}`:'Źródło oczekuje na kontrolę.'));
  const remove=node('button','Usuń źródło');remove.type='button';remove.onclick=()=>{box.remove();markDirty();};box.append(remove);$('sources').append(box);
}
function markDirty(){dirty=true;updateActions();}
function updateActions(){
  if(!current)return;
  $('verify').disabled=dirty||current.cc_review_status!=='draft'||!!current.blocked_reason||!$('facts').checked||!$('links').checked||!$('sentences').checked;
  $('approve').disabled=dirty||current.cc_review_status!=='draft'||current.cc_verification_status!=='verified'||!!current.blocked_reason||!$('style').checked;
  $('publish').disabled=dirty||!current.publish_enabled||current.cc_review_status!=='approved'||current.publication_status==='published';
  $('length').textContent=`${$('short').value.length}/220`;
}
function show(row){
  current=row;dirty=false;$('editor').hidden=false;$('history-button').hidden=false;$('history').replaceChildren();
  $('title').textContent=row.name;$('identity').textContent=`${row.island} · UUID ${row.entity_id} · rewizja ${row.cc_revision}`;
  $('status').textContent=[row.cc_verification_status,row.cc_review_status,row.publication_status].map(x=>labels[x]||x).join(' · ');
  $('blocked').textContent=row.blocked_reason?`Zablokowane: ${row.blocked_reason}`:'';
  $('short').value=row.short_description;$('body').value=row.body||'';$('sources').replaceChildren();row.cc_sources.forEach(sourceRow);
  for(const id of ['facts','links','sentences','style'])$(id).checked=false;
  $('publish-help').textContent=row.publish_enabled?'Publikacja udostępnia zatwierdzoną wersję na stronie.':'Publikacja oczekuje na uruchomienie wydania. Możesz przygotowywać szkice i zatwierdzenia.';
  updateActions();
}
async function load(keep=false){
  const data=await api('?'+new URLSearchParams({q:$('q').value,island:$('island').value,state:$('state').value,offset,limit:50}));total=data.total;$('list').replaceChildren();
  for(const row of data.items){const b=node('button',`${row.name} · ${labels[row.cc_verification_status]||row.cc_verification_status}`);b.type='button';b.onclick=()=>{if(!dirty||confirm('Porzucić niezapisane zmiany?'))show(row);};$('list').append(b);}
  $('page').textContent=` ${offset+1}–${Math.min(offset+50,total)} / ${total} `;$('prev').disabled=offset===0;$('next').disabled=offset+50>=total;
  if(!keep){if(data.items[0])show(data.items[0]);else{current=null;$('editor').hidden=true;$('history-button').hidden=true;$('title').textContent='Brak wyników';$('identity').textContent='';$('status').textContent='';$('blocked').textContent='';}}
  $('message').textContent='Wczytano opisy. Zapis tworzy nową rewizję i wymaga ponownego sprawdzenia.';
}
function version(){const editor=$('actor').value.trim();if(editor.length<2)throw Error('Podaj osobę redagującą / zatwierdzającą.');return {editor,expected_fingerprint:current.fingerprint};}
$('search-form').onsubmit=e=>{e.preventDefault();if(dirty&&!confirm('Porzucić niezapisane zmiany?'))return;offset=0;task(()=>load());};
$('prev').onclick=()=>{if(!dirty||confirm('Porzucić niezapisane zmiany?')){offset=Math.max(0,offset-50);task(()=>load());}};
$('next').onclick=()=>{if(!dirty||confirm('Porzucić niezapisane zmiany?')){offset+=50;task(()=>load());}};
$('add-source').onclick=()=>{sourceRow();markDirty();};
for(const id of ['short','body','sources'])$(id).addEventListener('input',markDirty);
for(const id of ['facts','links','sentences','style'])$(id).onchange=updateActions;
$('editor').onsubmit=e=>{e.preventDefault();task(async()=>{const sources=[...document.querySelectorAll('.lugares-source')].map(box=>Object.fromEntries([...box.querySelectorAll('input')].map(i=>[i.dataset.field,i.value])));const row=await api('/'+current.entity_id,'PUT',{...version(),short_description:$('short').value,detailed_description:$('body').value,sources});show(row);await load(true);$('message').textContent='Zapisano nową rewizję. Sprawdź fakty i źródła przed zatwierdzeniem.';});};
for(const action of ['verify','approve','publish'])$(action).onclick=()=>task(async()=>{
  if(action==='publish'&&!confirm(`Opublikować „${current.name}”, rewizja ${current.cc_revision}?`))return;
  const row=await api('/'+current.entity_id+'/actions','POST',{...version(),action,facts_checked:$('facts').checked,sources_checked:$('links').checked,sentence_count_checked:$('sentences').checked,style_approved:$('style').checked});show(row);await load(true);$('message').textContent=action==='publish'?'Opublikowano zatwierdzoną rewizję.':action==='approve'?'Zatwierdzono redakcyjnie. Publikacja jest osobną czynnością.':'Zapisano potwierdzenie weryfikacji redakcyjnej.';
});
$('history-button').onclick=()=>task(async()=>{const data=await api('/'+current.entity_id+'/history');$('history').replaceChildren();for(const row of data.items){const d=node('details'),s=node('summary',`Rewizja ${row.cc_revision} · ${labels[row.cc_review_status]||row.cc_review_status} · ${labels[row.publication_status]||row.publication_status}`);d.append(s,node('p',row.short_description),node('p',row.body||''),node('p',row.cc_reviewed_by?`Zatwierdziła: ${row.cc_reviewed_by} · ${row.cc_reviewed_at}`:'Brak zatwierdzenia'));for(const source of row.cc_sources)d.append(node('p',`${source.title||''}: ${source.url} · ${source.checked_at||'brak kontroli'}`));$('history').append(d);}});
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
task(()=>load());
