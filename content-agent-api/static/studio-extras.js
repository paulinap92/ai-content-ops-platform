(() => {
  "use strict";
  const $=id=>document.getElementById(id);
  const req=async(url,options)=>{const r=await fetch(url,options);const data=await r.json();if(!r.ok)throw Error(data.detail||`HTTP ${r.status}`);return data;};
  async function loadDrafts() {
    try {
      const data = await req("/api/studio/social/drafts");
      const list = $("studio-social-list");list.replaceChildren();
      if (!data.drafts.length) { list.textContent = "No social drafts yet.";return; }
      data.drafts.forEach(draft => {
        const card=document.createElement("article");card.className="panel";card.style.padding="12px";
        const heading=document.createElement("strong");heading.textContent=draft.title;
        const line=document.createElement("p");line.className="muted";line.textContent=`${draft.platforms.join(" + ")} · ${draft.status}`;
        const caption=document.createElement("p");caption.textContent=draft.caption;
        card.append(heading,line,caption);list.appendChild(card);
      });
    } catch(err) { $("studio-social-status").textContent=err.message; }
  }
  document.addEventListener("DOMContentLoaded",()=>{
    document.querySelector('[data-view="social"]')?.addEventListener("click",loadDrafts);
    $("studio-social-form").addEventListener("submit",async e=>{
      e.preventDefault();
      const platforms=["instagram","facebook"].filter(x=>$("studio-social-"+x).checked);
      if(!platforms.length){$("studio-social-status").textContent="Choose at least one platform.";return;}
      const payload={title:$("studio-social-title").value.trim(),caption:$("studio-social-caption").value.trim(),image_url:$("studio-social-image").value.trim()||null,platforms};
      try{
        await req("/api/studio/social/drafts",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
        $("studio-social-status").textContent="Zapisano szkic. Nie opublikowano go w mediach społecznościowych.";
        e.target.reset();await loadDrafts();
      }catch(err){$("studio-social-status").textContent=err.message;}
    });
  });
})();
