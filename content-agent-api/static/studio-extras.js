(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const channels=['instagram','facebook','whatsapp'];
  const names={instagram:'Instagram',facebook:'Facebook',whatsapp:'WhatsApp'};
  const labels={draft:'Szkic',ready:'Gotowy',archived:'Archiwum'};
  const model={drafts:[],current:null,filter:'draft',channel:'instagram',dirty:false,busy:false};
  async function req(url,options={}){
    const response=await fetch(url,{...options,headers:{...(options.body?{'Content-Type':'application/json'}:{}),...options.headers}});
    if(response.status===401){location.replace('/login');throw Error('Sesja wygasła. Zaloguj się ponownie.');}
    const data=await response.json();
    if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map(x=>x.msg).join(' · '):data.details?.join(' · ')||`Błąd ${response.status}`);
    return data;
  }
  const feedback=(message,error=false)=>{$('studio-social-status').textContent=message;$('studio-social-status').classList.toggle('error',error);};
  const textFor=(draft,channel)=>draft.captions?.[channel]?.trim()||draft.caption||'';
  const completed=(draft,channel)=>(draft?.history||[]).some(item=>item.platform===channel);
  const allCompleted=draft=>draft.platforms.every(channel=>completed(draft,channel));
  function values(){return{title:$('studio-social-title').value.trim(),caption:$('studio-social-caption').value.trim(),platforms:channels.filter(c=>$('studio-social-'+c).checked),image_url:$('studio-social-image').value||null,image_alt:$('social-image-alt').value,captions:Object.fromEntries(channels.map(c=>[c,$('social-caption-'+c).value]))};}
  function canDiscard(){return !model.dirty||window.confirm('Masz niezapisane zmiany. Otworzyć inny post i je odrzucić?');}
  function renderList(){
    const root=$('studio-social-list');root.replaceChildren();
    const query=$('social-search').value.toLocaleLowerCase();
    const rows=model.drafts.filter(d=>{
      const match=model.filter==='history'?(d.history||[]).length>0:model.filter==='ready'?d.status==='ready'&&!allCompleted(d):d.status===model.filter;
      return match&&(`${d.title} ${d.caption}`).toLocaleLowerCase().includes(query);
    });
    if(!rows.length){const empty=document.createElement('p');empty.className='muted';empty.textContent='Brak materiałów w tym widoku.';root.append(empty);return;}
    for(const draft of rows){const button=document.createElement('button');button.type='button';button.className='draft-item'+(draft.id===model.current?.id?' active':'');const title=document.createElement('div');title.className='draft-item-title';title.textContent=draft.title;const meta=document.createElement('div');meta.className='draft-item-meta';meta.textContent=draft.platforms.map(c=>names[c]).join(' · ')+(draft.history?.length?` · ${draft.history.length} publikacji`:'');button.append(title,meta);button.onclick=()=>{if(canDiscard())openDraft(draft);};root.append(button);}
  }
  function setFilter(filter){model.filter=filter;document.querySelectorAll('[data-social-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.socialFilter===filter)));renderList();}
  async function refresh(){const result=await req('/api/studio/social/drafts');model.drafts=result.drafts;renderList();}
  function openDraft(draft=null){
    model.current=draft;model.dirty=false;
    $('studio-social-title').value=draft?.title||'';$('studio-social-caption').value=draft?.caption||'';
    $('studio-social-image').value=draft?.image_url||'';$('social-image-alt').value=draft?.image_alt||'';
    for(const c of channels){$('studio-social-'+c).checked=draft?draft.platforms.includes(c):c!=='whatsapp';$('social-caption-'+c).value=draft?.captions?.[c]||'';}
    model.channel=draft?.platforms?.[0]||'instagram';feedback('');renderList();render();
  }
  function render(){
    const draft=values(),channel=model.channel,content=textFor(draft,channel),saved=model.current;
    const archived=saved?.status==='archived',ready=saved?.status==='ready'&&!model.dirty&&!archived;
    $('social-form-heading').textContent=saved?'Edycja posta':'Nowy post';$('social-record-status').textContent=(labels[saved?.status]||'Szkic')+(model.dirty?' · niezapisane zmiany':'');
    $('social-record-status').className='status-pill '+(ready?'status-ready':'status-neutral');
    $('social-preview-caption').textContent=content||'Wpisz treść posta.';
    const image=$('social-preview-image');image.hidden=!draft.image_url;$('social-preview-placeholder').hidden=Boolean(draft.image_url);if(draft.image_url)image.src=draft.image_url;else image.removeAttribute('src');image.alt=draft.image_alt||'Zdjęcie posta';
    $('social-image-label').textContent=draft.image_url?(draft.image_alt||'Zdjęcie wybrane z biblioteki'):'Bez zdjęcia — Instagram wymaga zdjęcia.';
    $('social-remove-photo').classList.toggle('hidden',!draft.image_url);
    $('social-character-count').textContent=`${content.length}${channel==='instagram'?' / 2200':''} znaków`;$('social-character-count').classList.toggle('error',channel==='instagram'&&content.length>2200);
    document.querySelectorAll('[data-social-preview]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.socialPreview===channel)));
    const selected=draft.platforms.includes(channel),done=completed(saved,channel),available=ready&&selected&&!done&&!model.busy;
    const link=$('social-open-channel');link.textContent=channel==='whatsapp'?'Otwórz WhatsApp':'Otwórz Metricool';link.setAttribute('aria-disabled',String(!available));if(available)link.href=channel==='whatsapp'?'https://wa.me/?text='+encodeURIComponent(content):'https://app.metricool.com/';else link.removeAttribute('href');
    $('social-delivery-hint').textContent=done?'Publikacja w tym kanale została potwierdzona przez Ciebie.':!selected?'Ten kanał nie jest wybrany dla posta.':!ready?'Zapisz i zatwierdź post, aby przejść do wysyłania.':channel==='whatsapp'?'W WhatsApp wybierz odbiorcę i wyślij wiadomość. Do kanału możesz wkleić tekst; zdjęcie pobierz lub udostępnij poniżej.':'Skopiuj tekst i pobierz zdjęcie. W Metricool wybierz canarias.cerca i zaplanuj publikację. Otwarcie Metricool nie przenosi materiału automatycznie.';
    $('social-confirm-published').textContent=done?'Publikacja potwierdzona':`Potwierdź publikację · ${names[channel]}`;$('social-confirm-published').disabled=!available;
    $('social-share').hidden=!navigator.share;$('social-share').disabled=!available;
    $('social-copy-image').disabled=!draft.image_url||model.busy;$('social-download').disabled=!draft.image_url||model.busy;
    $('social-save').disabled=archived||model.busy;$('social-ready').disabled=archived||model.busy;$('social-archive').disabled=!saved||model.busy;$('social-archive').textContent=archived?'Przywróć szkic':'Archiwizuj';
    $('social-choose-photo').disabled=archived||model.busy;$('social-remove-photo').disabled=archived||model.busy;
    $('studio-social-form').querySelectorAll('input,textarea').forEach(el=>el.disabled=archived||model.busy);
    const history=$('social-record-history');history.replaceChildren();
    if(!saved?.history?.length)history.textContent='Brak potwierdzonych publikacji.';
    for(const item of saved?.history||[]){const row=document.createElement('details'),summary=document.createElement('summary'),text=document.createElement('p');const date=new Date(item.published_at);summary.textContent=`${names[item.platform]} · ${Number.isNaN(date.valueOf())?item.published_at:date.toLocaleString('pl-PL',{timeZone:'Atlantic/Canary'})} · potwierdzenie własne`;text.textContent=item.caption;row.append(summary,text);if(item.image_url){const a=document.createElement('a');a.textContent='Zdjęcie użyte w publikacji';a.href=item.image_url;a.target='_blank';a.rel='noopener noreferrer';row.append(a);}history.append(row);}
  }
  async function persist(){
    if(!$('studio-social-form').reportValidity())throw Error('Uzupełnij nazwę i treść posta.');
    const draft=values();if(!draft.platforms.length)throw Error('Wybierz przynajmniej jeden kanał.');
    const result=await req('/api/studio/social/drafts'+(model.current?'/'+model.current.id:''),{method:model.current?'PUT':'POST',body:JSON.stringify({...draft,...(model.current?{version:model.current.version}:{})})});
    model.current=result;model.dirty=false;await refresh();return result;
  }
  async function busy(work){if(model.busy)return;model.busy=true;try{render();await work();}catch(error){feedback(error.message,true);}finally{model.busy=false;render();}}
  async function action(type,platform){
    let current=model.current;
    if(type!=='restore'&&(model.dirty||!current))current=await persist();
    if(!current)throw Error('Najpierw zapisz post.');
    const result=await req(`/api/studio/social/drafts/${current.id}/actions`,{method:'POST',body:JSON.stringify({action:type,platform,version:current.version})});
    model.current=result;model.dirty=false;await refresh();return result;
  }
  async function copy(text){if(!navigator.clipboard?.writeText)throw Error('Przeglądarka nie udostępnia schowka. Zaznacz i skopiuj treść w podglądzie.');await navigator.clipboard.writeText(text);feedback('Skopiowano do schowka.');}
  async function photoFile(){const draft=values();const response=await fetch('/site/api/media/file?'+new URLSearchParams({url:draft.image_url}));if(!response.ok)throw Error('Nie udało się pobrać zdjęcia.');const blob=await response.blob();if(!blob.type.startsWith('image/'))throw Error('Pod wybranym adresem nie ma zdjęcia.');return new File([blob],'canarias-cerca.'+(blob.type==='image/png'?'png':blob.type==='image/webp'?'webp':'jpg'),{type:blob.type});}
  document.addEventListener('DOMContentLoaded',()=>{
    const form=$('studio-social-form');
    document.querySelector('[data-view="social"]').addEventListener('click',()=>refresh().catch(e=>feedback(e.message,true)));
    form.addEventListener('input',()=>{model.dirty=true;render();});form.addEventListener('change',()=>{model.dirty=true;render();});
    form.addEventListener('submit',e=>{e.preventDefault();busy(async()=>{await persist();setFilter('draft');feedback('Szkic zapisany. Materiał nie został opublikowany.');});});
    $('social-new').onclick=()=>{if(canDiscard()){openDraft();setFilter('draft');$('studio-social-title').focus();}};
    $('social-refresh').onclick=()=>busy(async()=>{await refresh();feedback('Lista odświeżona.');});
    document.querySelectorAll('[data-social-filter]').forEach(b=>b.onclick=()=>setFilter(b.dataset.socialFilter));$('social-search').oninput=renderList;
    document.querySelectorAll('[data-social-preview]').forEach(b=>b.onclick=()=>{model.channel=b.dataset.socialPreview;render();});
    $('social-ready').onclick=()=>busy(async()=>{await action('ready');setFilter('ready');feedback('Post zatwierdzony. Wybierz kanał w podglądzie i przejdź do publikacji.');});
    $('social-archive').onclick=()=>busy(async()=>{const archived=model.current?.status==='archived';await action(archived?'restore':'archive');setFilter(archived?'draft':'archived');feedback(archived?'Przywrócono szkic.':'Przeniesiono do archiwum. Historia została zachowana.');});
    $('social-choose-photo').onclick=()=>window.dispatchEvent(new CustomEvent('cc-social-open-photos'));
    $('social-remove-photo').onclick=()=>{$('studio-social-image').value='';$('social-image-alt').value='';model.dirty=true;render();};
    $('social-copy').onclick=()=>copy(textFor(values(),model.channel)).catch(e=>feedback(e.message,true));
    $('social-copy-image').onclick=()=>copy(values().image_url||'').catch(e=>feedback(e.message,true));
    $('social-download').onclick=()=>busy(async()=>{const file=await photoFile(),url=URL.createObjectURL(file),link=document.createElement('a');link.href=url;link.download=file.name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);feedback('Zdjęcie przygotowane do pobrania.');});
    $('social-share').onclick=async()=>{try{const draft=values(),files=draft.image_url?[await photoFile()]:[];if(files.length&&(!navigator.canShare||!navigator.canShare({files})))throw Error('Ta przeglądarka nie udostępnia zdjęć. Użyj przycisków pobierania i kopiowania.');await navigator.share({text:textFor(draft,model.channel),...(files.length?{files}:{})});feedback('Udostępnianie zakończone. Potwierdź publikację dopiero po sprawdzeniu kanału.');}catch(e){if(e.name!=='AbortError')feedback(e.message,true);}};
    $('social-confirm-published').onclick=()=>{if(window.confirm(`Czy materiał został już opublikowany w ${names[model.channel]}? To zapisze potwierdzenie w historii, bez wysyłania posta.`))busy(async()=>{await action('confirm-published',model.channel);setFilter('history');feedback('Zapisano Twoje potwierdzenie publikacji. Tekst i zdjęcie pozostają w historii.');});};
    window.addEventListener('cc-social-image-selected',event=>{$('studio-social-image').value=event.detail.url;$('social-image-alt').value=event.detail.alt||'';model.dirty=true;render();feedback('Zdjęcie przypisane do posta. Zapisz szkic, aby zachować zmianę.');});
    window.addEventListener('beforeunload',e=>{if(model.dirty){e.preventDefault();e.returnValue='';}});
    openDraft();
  });
})();
