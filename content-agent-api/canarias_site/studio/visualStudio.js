// The preview shares the production route manifest and production renderers.
// Messages carry record identities/draft copy only, never editor credentials.
const SITE='https://www.canariascerca.es';
export function createVisualStudio({api,node,onSelect,onNavigate,onExternal,message}) {
 const workspace=document.getElementById('workspace'),tree=document.getElementById('visual-tree'),frame=document.getElementById('visual-frame');
 const status=document.getElementById('visual-status');
 let manifest=null,current=null,selection=0;
 function enable(){workspace.classList.add('visual-mode');document.getElementById('visual-preview').hidden=false;}
 function preview(route) {
  enable();current=route;
  const u=new URL(route.path,SITE);u.searchParams.set('studio','1');u.searchParams.set('studio_origin',location.origin);
  frame.src=u.href;document.getElementById('visual-url').textContent=route.path;
  status.textContent='Podgląd opublikowanej strony. Kliknij tekst, kartę, zdjęcie lub pinezkę, aby otworzyć edytor.';
 }
 function showRoutes(){
  tree.replaceChildren();
  const scope=document.getElementById('tree-scope').value;
  const routes=manifest.routes.filter(r=>scope==='global'?!r.island:r.island===scope);
  if(scope==='global'){
   const home=node('button','Strona startowa',{type:'button'});home.onclick=()=>preview(manifest.routes[0]);tree.append(home);
   for(const island of [...new Set(manifest.routes.map(r=>r.island).filter(Boolean))]){
    const b=node('button',island.replaceAll('-',' '),{type:'button'});b.onclick=()=>{document.getElementById('tree-scope').value=island;showRoutes();preview(manifest.routes.find(r=>r.island===island&&r.section==='explore'&&!r.resource));};tree.append(b);
   }return;
  }
  for(const section of [...new Set(routes.map(r=>r.section))]){
   const group=node('details');group.open=section==='explore';group.append(node('summary',section));
   for(const route of routes.filter(r=>r.section===section)){
    const b=node('button',route.title+(route.mode==='automatic'?' · automat':''),{type:'button',title:route.api+' → '+route.source});
    b.onclick=async()=>{preview(route);try{await onNavigate(route);}catch(e){message(e.message,true);}};group.append(b);
   }tree.append(group);
  }
 }
 async function load(){
  try{manifest=await api('/site-manifest');document.getElementById('manifest-source').textContent='Aktualizowane z '+manifest.generated_from+' · '+manifest.routes.length+' widoków';showRoutes();preview(manifest.routes[0]);}
  catch(e){status.textContent=e.message;}
 }
 async function catalog(){
  enable();const data=await api('/lugares-catalog');
  document.getElementById('manifest-source').textContent=`${data.published} opisy na stronie · ${data.blocked} wstrzymanych · ${data.overlay_rows} nakładki`;
  tree.replaceChildren();const search=node('input',undefined,{type:'search',placeholder:'Szukaj miejsca lub UUID…','aria-label':'Szukaj w 380 miejscach'}),filter=node('select',undefined,{'aria-label':'Stan miejsca'});filter.append(new Option('Wszystkie',''),new Option('Na stronie','published'),new Option('Wstrzymane','blocked'));
  const list=node('div');tree.append(search,filter,list);
  function draw(){list.replaceChildren();for(const item of data.items.filter(i=>(!filter.value||i.state===filter.value)&&(!search.value||(i.name+' '+i.canonical_id).toLowerCase().includes(search.value.toLowerCase())))){
   const b=node('button',item.name,{type:'button'});b.append(node('small',item.island+' · '+(item.state==='blocked'?'Wstrzymane':'Na stronie')));b.onclick=async()=>{
    try{
     if(manifest){const route=manifest.routes.find(r=>r.island===item.island&&r.section==='explore'&&r.resource==='places');preview({...route,path:route.path+'?punto='+encodeURIComponent(item.canonical_id)});}
     await onSelect({kind:'explore',island:item.island,resource:item.resource,record_key:item.canonical_id});
    }catch(e){message(e.message,true);}
   };list.append(b);
  }}search.oninput=filter.onchange=draw;draw();
 }
 window.addEventListener('message',async event=>{
  if(event.origin!==SITE||event.source!==frame.contentWindow||!['cc-studio-ready','cc-studio-select'].includes(event.data?.type))return;
  const {route,selection:target}=event.data;if(!route?.valid)return;
  current=manifest?.routes.find(r=>r.island===route.island&&r.section===route.section&&r.resource===route.resource)||current;
  if(event.data.type==='cc-studio-ready'){status.textContent='Podgląd połączony. Kliknij element, aby go edytować.';return;}
  const token=++selection;
  try{
   if(target?.kind==='settings'){await onNavigate(current,target.copy_key);return;}
   if(target?.record_key){await onSelect({kind:target.kind,island:route.island,resource:target.resource,record_key:target.record_key});if(token===selection)status.textContent='Otworzono wybrany element. Zapis szkicu zachowuje wersję widoczną na stronie.';}
   else {await onNavigate(current);status.textContent=current.mode==='automatic'?'Pomiary są automatyczne. Możesz zmieniać teksty i widoczność sekcji.':'Wybrano ustawienia widoku.';}
  }catch(e){message(e.message,true);}
 });
 document.getElementById('visual-reload').onclick=()=>frame.contentWindow?.postMessage({type:'cc-studio-refresh'},SITE);
 document.getElementById('visual-draft').onclick=()=>onExternal('draft-preview');
 document.getElementById('visual-close').onclick=()=>{workspace.classList.remove('visual-mode');document.getElementById('visual-preview').hidden=true;};
 document.getElementById('tree-scope').addEventListener('change',()=>manifest&&showRoutes());
 return {load,catalog,open:()=>{enable();manifest?showRoutes():load();},draft:(identity,payload)=>{frame.contentWindow?.postMessage({type:'cc-studio-draft',identity,payload},SITE);status.textContent='Podgląd szkicu — zmiany nie są jeszcze opublikowane.';},refresh:()=>{if(frame.src)frame.contentWindow?.postMessage({type:'cc-studio-refresh'},SITE);}};
}
