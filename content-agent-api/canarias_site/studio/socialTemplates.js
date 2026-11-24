export function createSocialTemplates(root,{api}){

const C={dark:'#0F3D3E',teal:'#2A9D8F',blue:'#7EC8E3',gold:'#F4B942',sand:'#EDE7DC',white:'#FFFFFF'};
const formats={ig:[1080,1350],fb:[1200,630],wa:[1080,1080],story:[1080,1920]};
const examples={guia:['GUÍA','Tu próxima aventura en Canarias','Consejos para descubrir las islas'],noticias:['NOTICIAS','Título de la noticia','Breve resumen de la actualidad canaria.'],eventos:['EVENTOS','Planes para el fin de semana','Fecha · Municipio · Isla'],lugares:['LUGARES','Un rincón por descubrir','Nombre del lugar · Isla'],datos:['DATOS','Título del informe','Periodo · Fuente de los datos']};
const $=id=>root.querySelector('#tpl-'+id), canvas=$('canvas'), ctx=canvas.getContext('2d');let photo=null, identity=null,credit='',busy=false,loading=false,failed=false,seq=0,asset=null,lastDraft=null;const logo=new Image(),decor=new Image();logo.src=new URL('./social-logo.png',import.meta.url).href;decor.src=new URL('./social-ai-decor.jpg',import.meta.url).href;
function text(t,x,y,size,weight=400,color=C.dark){ctx.font=`${weight} ${size}px Arial, sans-serif`;ctx.fillStyle=color;ctx.textBaseline='top';ctx.fillText(t,x,y)}
function rect(x,y,w,h,c){ctx.fillStyle=c;ctx.fillRect(x,y,w,h)}
function wrap(str,max){let lines=[],line='';for(let word of String(str).trim().split(/\s+/)){if(!word)continue;let next=line?line+' '+word:word;if(ctx.measureText(next).width>max&&line){lines.push(line);line=word}else line=next;while(ctx.measureText(line).width>max&&line.length>1){let n=1;while(n<line.length&&ctx.measureText(line.slice(0,n+1)).width<=max)n++;lines.push(line.slice(0,n));line=line.slice(n)}}if(line)lines.push(line);return lines}
function block(str,x,y,w,maxH,size,weight,color){let lines,step;for(;size>=18;size--){ctx.font=`${weight} ${size}px Arial, sans-serif`;lines=wrap(str,w);step=size*1.14;if(lines.length*step<=maxH)break}lines=lines.slice(0,Math.max(1,Math.floor(maxH/step)));lines.forEach((l,i)=>text(l,x,y+i*step,size,weight,color));return lines.length*step}
function logoAt(x,y,d){if(!logo.complete||!logo.naturalWidth)return;ctx.save();ctx.beginPath();ctx.arc(x+d/2,y+d/2,d/2,0,Math.PI*2);ctx.clip();const s=logo.naturalWidth*0.95,off=(logo.naturalWidth-s)/2;ctx.drawImage(logo,off,off,s,s,x,y,d,d);ctx.restore()}
function imageArea(x,y,w,h,kind){rect(x,y,w,h,'#d5e9e8');if(photo){const a=photo.naturalWidth/photo.naturalHeight,b=w/h;let sx=0,sy=0,sw=photo.naturalWidth,sh=photo.naturalHeight;if(kind==='datos'){let scale=Math.min(w/sw,h/sh);rect(x,y,w,h,C.white);ctx.drawImage(photo,x+(w-sw*scale)/2,y+(h-sh*scale)/2,sw*scale,sh*scale)}else{if(a>b){sw=sh*b;sx=(photo.naturalWidth-sw)/2}else{sh=sw/b;sy=(photo.naturalHeight-sh)/2}ctx.drawImage(photo,sx,sy,sw,sh,x,y,w,h)}return}
if(kind==='datos'){rect(x,y,w,h,'#f8f6f0');text('ESPACIO PARA GRÁFICO',x+w*.08,y+h*.08,Math.min(w*.042,h*.09),700);for(let i=0;i<3;i++)rect(x+w*(.24+i*.19),y+h*(.65-i*.15),w*.12,h*(.18+i*.15),C.teal);return}
ctx.strokeStyle='#699b9a';ctx.lineWidth=Math.max(2,w*.004);let d=Math.min(w,h)*.18,cx=x+w/2,cy=y+h/2-d*.35;ctx.strokeRect(cx-d*.6,cy-d*.5,d*1.2,d);ctx.beginPath();ctx.moveTo(cx-d*.6,cy+d*.35);ctx.lineTo(cx-d*.1,cy-d*.12);ctx.lineTo(cx+d*.22,cy+d*.18);ctx.lineTo(cx+d*.6,cy-d*.08);ctx.stroke();ctx.beginPath();ctx.arc(cx+d*.27,cy-d*.23,d*.095,0,Math.PI*2);ctx.stroke();ctx.font=`600 ${Math.max(18,d*.23)}px Arial`;let label='ESPACIO PARA FOTO';text(label,cx-ctx.measureText(label).width/2,cy+d*.76,Math.max(18,d*.23),600,'#477674')}
function draw(){const k=$('type').value,[w,h]=formats[$('format').value];canvas.width=w;canvas.height=h;$('size').textContent=w+' × '+h+' px';syncButtons();if($('style').value==='ai'){drawAI(k,w,h);return;}rect(0,0,w,h,C.sand);let m=Math.round(w*.055), landscape=w>h, story=h/w>1.6, photoX,photoY,photoW,photoH;let title=$('title').value,detail=$('detail').value;
if(landscape){let split=Math.round(w*.53);photoX=split;photoY=0;photoW=w-split;photoH=h;imageArea(photoX,photoY,photoW,photoH,k);logoAt(m,28,86);text('CANARIAS CERCA',m+104,56,25,600);text(examples[k][0],m,160,23,700,C.teal);let tw=split-m*1.8;let th=block(title,m,202,tw,165,58,700,C.dark);rect(m,202+th+10,66,5,C.gold);block(detail,m,202+th+32,tw,Math.max(22,h-90-202-th-32),29,400,C.dark);text('canariascerca.es',m,h-63,25,600);return}
let header=story?225:162;logoAt(m,story?74:28,story?118:105);text('CANARIAS CERCA',m+(story?142:129),story?117:61,story?36:32,600);photoX=0;photoY=header;photoW=w;photoH=Math.round(h*(story?.49:($('format').value==='wa'?.49:.51)));imageArea(photoX,photoY,photoW,photoH,k);let top=photoY+photoH+(story?52:35);text(examples[k][0],m,top,story?31:26,700,C.teal);let ty=top+(story?60:49),footer=story?h-177:h-84;let maxTitle=Math.min(story?200:150,Math.max(70,footer-ty-92));let th=block(title,m,ty,w-2*m,maxTitle,story?78:67,700,C.dark);let line=ty+th+14;rect(m,line,86,6,C.gold);block(detail,m,line+25,w-2*m,Math.max(26,footer-line-35),story?37:32,400,C.dark);rect(m,footer-18,w-2*m,2,'#c3c9ba');text('canariascerca.es',m,footer+9,story?33:28,600,C.dark);
}
function setExample(){identity=null;credit='';seq++;loading=false;failed=false;asset=null;lastDraft=null;$('url').value='';$('caption').value='';$('source').textContent='Samodzielna grafika';let e=examples[$('type').value];$('title').value=e[1];$('detail').value=e[2];photo=null;$('photo').value='';draw()}


function round(x,y,w,h,r,color){ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fillStyle=color;ctx.fill()}
function drawAI(k,w,h){
 const m=Math.round(w*.05),wide=w>h,story=h/w>1.6,grad=ctx.createLinearGradient(0,0,w,h);
 grad.addColorStop(0,'#FFF5E4');grad.addColorStop(.56,C.sand);grad.addColorStop(1,C.blue);rect(0,0,w,h,grad);
 if(decor.naturalWidth){let dx=w*.66,dw=w-dx,dh=wide?h*.27:Math.min(h*.23,w*.25);ctx.save();ctx.globalAlpha=.78;ctx.drawImage(decor,dx,0,dw,dh);ctx.restore();let fade=ctx.createLinearGradient(dx,0,w,0);fade.addColorStop(0,'#FFF5E4');fade.addColorStop(.67,'rgba(255,245,228,0)');rect(dx,0,dw,dh,fade);}
 let d=wide?76:story?118:104;logoAt(m,wide?20:story?75:30,d);text('CANARIAS CERCA',m+d+19,wide?44:story?116:63,wide?28:34,700);
 let cy=wide?130:story?225:175,cs=wide?22:28;ctx.font='700 '+cs+'px Arial';let cw=ctx.measureText(examples[k][0]).width+42;round(m,cy,cw,cs+24,22,C.teal);text(examples[k][0],m+21,cy+10,cs,700,C.white);
 let title=$('title').value,detail=$('detail').value,ty=cy+cs+48;
 if(wide){let left=w*.47,tw=left-m-23,th=block(title,m,ty,tw,150,58,700,C.dark);rect(m,ty+th+10,84,6,C.gold);block(detail,m,ty+th+29,tw,Math.max(20,h-105-ty-th-29),28,400,C.dark);
   round(left-6,124,w-left-m+12,h-124-104,27,C.white);ctx.save();ctx.beginPath();ctx.roundRect(left,130,w-left-m,h-130-110,21);ctx.clip();imageArea(left,130,w-left-m,h-130-110,k);ctx.restore();
 }else{let maxT=story?180:$('format').value==='wa'?105:140,th=block(title,m,ty,w-2*m,maxT,story?76:64,700,C.dark);rect(m,ty+th+10,88,6,C.gold);let dy=ty+th+30,dh=block(detail,m,dy,w-2*m,story?88:65,story?36:30,400,C.dark),py=dy+Math.max(dh,35)+25,foot=story?h-208:h-102,ph=foot-py-12;if(ph>0){round(m-7,py-7,w-2*m+14,ph+14,33,C.white);ctx.save();ctx.beginPath();ctx.roundRect(m,py,w-2*m,ph,26);ctx.clip();imageArea(m,py,w-2*m,ph,k);ctx.restore();}}
 ctx.save();ctx.strokeStyle='rgba(255,255,255,.65)';ctx.lineWidth=3;for(let i=0;i<5;i++){ctx.beginPath();ctx.moveTo(0,h-20-i*16);ctx.bezierCurveTo(w*.33,h-150-i*16,w*.6,h+25-i*16,w,h-100-i*16);ctx.stroke()}ctx.restore();
 const fy=story?h-175:h-80,fh=story?110:70;round(m,fy,w-2*m,fh,fh/2,'#FFF8EC');text('canariascerca.es',m+24,fy+(fh-32)/2,story?34:28,700,C.dark);
 const cta=k==='eventos'?'Ver planes':k==='lugares'?'Descubrir':k==='datos'?'Ver datos':'Leer más';ctx.font='700 27px Arial';const bw=ctx.measureText(cta+'  ›').width+40,bx=w-m-bw-9;round(bx,fy+9,bw,fh-18,26,C.gold);text(cta+'  ›',bx+20,fy+(fh-27)/2,27,700,C.dark);
}
function plain(v){return typeof v==='string'?v.replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim():''}
function clip(v,n){const s=plain(v);return s.length>n?s.slice(0,n-1).trimEnd()+'…':s}
const kindMap={news:'noticias',calendar:'eventos',explore:'lugares',guide:'guia',datos:'datos'};
const islands=['tenerife','gran-canaria','lanzarote','fuerteventura','la-palma','la-gomera','el-hierro','la-graciosa'];
const status=(v,error=false)=>{$('status').textContent=v;$('status').classList.toggle('inspection-error',error)};
function syncButtons(){for(const id of ['save','library','social'])$(id).disabled=busy||loading||failed||!logo.naturalWidth||!$('title').value.trim();if(!photo){$('library').disabled=true;$('social').disabled=true}}
function redraw(){asset=null;lastDraft=null;draw()}
async function decodeImage(blob){if(!blob.type.startsWith('image/')||blob.size>20_000_000)throw Error('Wybierz obraz do 20 MB.');const url=URL.createObjectURL(blob);try{return await new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=()=>reject(Error('Nie udało się otworzyć obrazu.'));im.src=url;})}finally{URL.revokeObjectURL(url)}}
async function loadPhoto(value,isFile=false){
 const token=++seq;photo=null;asset=null;lastDraft=null;failed=false;loading=Boolean(value);draw();if(!value)return;
 try{let blob=value;if(!isFile){const parsed=new URL(value,location.origin);if(parsed.protocol!=='https:'&&parsed.origin!==location.origin)throw Error('Adres musi używać HTTPS.');let r=await fetch('/site/api/media/file?'+new URLSearchParams({url:parsed.href}));if(!r.ok)r=await fetch(parsed.href,{mode:'cors',credentials:parsed.origin===location.origin?'same-origin':'omit'});if(!r.ok)throw Error('Zdjęcie niedostępne.');blob=await r.blob();}const im=await decodeImage(blob);if(token!==seq)return;photo=im;status('Zdjęcie wczytane.')}
 catch(error){if(token!==seq)return;failed=true;status('Nie udało się wczytać zdjęcia. Wybierz lokalny plik lub usuń adres.',true)}
 finally{if(token===seq){loading=false;draw()}}
}
function open(record=null,type='noticias'){
 $('type').value=kindMap[record?.identity?.kind]||type;setExample();
 if(!record)return;
 const v=record.draft||{},id=record.identity||{};identity=id.record_key?{kind:id.kind,island:id.island,resource:id.resource,record_key:id.record_key}:null;credit=plain(v.image_credit);
 $('source').textContent='Grafika dla: '+plain(v.title||v.name);$('title').value=clip(v.title||v.name||examples[$('type').value][1],125);
 const detail=id.kind==='calendar'?[v.start_date,v.location||v.venue,id.island?.replaceAll('-',' ')].map(plain).filter(Boolean).join(' · '):v.short_description||v.summary||v.description||v.detailed_description;
 $('detail').value=clip(detail||examples[$('type').value][2],160);$('caption').value=clip(v.summary||v.short_description||v.description||v.detailed_description,1800);
 $('island').value=islands.includes(id.island)?id.island:'tenerife';$('url').value=plain(v.image_url);draw();if($('url').value)void loadPhoto($('url').value);
}
const filename=()=>['canarias-cerca',$('type').value,$('style').value,$('format').value].join('-')+'.png';
const getBlob=()=>new Promise((res,rej)=>canvas.toBlob(b=>b?res(b):rej(Error('Nie udało się wygenerować PNG.')),'image/png'));
const encode=b=>new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(String(r.result).split(',')[1]);r.onerror=rej;r.readAsDataURL(b)});
async function saveAsset(){
 if(asset)return asset;const blob=await getBlob();if(blob.size>5_000_000)throw Error('PNG przekracza limit 5 MB.');
 asset=await api('/media',{method:'POST',body:JSON.stringify({island:$('island').value,filename:filename(),data:await encode(blob),alt:clip($('title').value,300),credit:clip(['Canarias Cerca',credit].filter(Boolean).join(' · '),200),social_context:{category:$('type').value,style:$('style').value,format:$('format').value,record:identity}})});return asset;
}
async function action(fn){if(busy||loading||failed||!logo.naturalWidth)return;busy=true;syncButtons();const inputs=[...root.querySelectorAll('input,textarea,select')];inputs.forEach(e=>e.disabled=true);try{await fn()}catch(e){status(e.message,true)}finally{inputs.forEach(e=>e.disabled=false);busy=false;syncButtons()}}
for(const id of ['type','format','style','title','detail'])$(id).addEventListener(id==='title'||id==='detail'?'input':'change',redraw);
$('island').onchange=()=>{asset=null;lastDraft=null};$('caption').oninput=()=>{lastDraft=null};
$('reset').onclick=()=>setExample();$('photo').onchange=()=>{$('url').value='';credit='';void loadPhoto($('photo').files[0],true)};
$('load-url').onclick=()=>{credit='';$('photo').value='';void loadPhoto($('url').value.trim())};$('url').onchange=()=>{credit='';$('photo').value='';void loadPhoto($('url').value.trim())};
$('clear').onclick=()=>{$('url').value='';$('photo').value='';credit='';void loadPhoto(null)};
$('save').onclick=()=>action(async()=>{const u=URL.createObjectURL(await getBlob()),a=document.createElement('a');a.href=u;a.download=filename();a.click();setTimeout(()=>URL.revokeObjectURL(u),2000);status('PNG wygenerowany.')});
$('library').onclick=()=>action(async()=>{if(!photo)throw Error('Dodaj zdjęcie lub wykres.');await saveAsset();status('Grafika w bibliotece. Nic nie opublikowano.')});
$('social').onclick=()=>action(async()=>{if(!photo)throw Error('Dodaj zdjęcie lub wykres.');const title=$('title').value.trim(),caption=($('caption').value.trim()||[title,$('detail').value].filter(Boolean).join('\n\n'))+'\n\nhttps://canariascerca.es',key=JSON.stringify([title,caption,filename(),$('island').value]);if(lastDraft===key){status('Ten szkic już zapisano. Otwórz Social Media.');return}const saved=await saveAsset(),platform={ig:'instagram',fb:'facebook',wa:'whatsapp',story:'whatsapp'}[$('format').value];const r=await fetch('/api/studio/social/drafts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,caption,platforms:[platform],image_url:saved.url,image_alt:title,captions:{}})});if(!r.ok)throw Error('Grafika jest w bibliotece, ale szkic nie został zapisany.');lastDraft=key;status('Szkic Social Media zapisany. Zatwierdź go osobno przed publikacją.')});
logo.onload=draw;logo.onerror=()=>{status('Nie udało się wczytać oryginalnego logo. Eksport zablokowany.',true);syncButtons()};decor.onload=draw;open();
return {open};

}
