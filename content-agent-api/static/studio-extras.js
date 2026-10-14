(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  let page = 0, count = 0, collection = "";
  const pageSize = 25;
  const req = async (url, options) => {
    const res = await fetch(url, options);
    let body = await res.json().catch(() => ({}));
    if (!res.ok) throw Error(body.detail || `HTTP ${res.status}`);
    return body;
  };
  const td = (row, value) => {
    const cell = document.createElement("td");
    cell.style.cssText = "padding:10px;border-bottom:1px solid #7774;vertical-align:top";
    cell.textContent = typeof value === "object" ? JSON.stringify(value) : String(value ?? "—");
    row.appendChild(cell);
  };
  async function loadCollections() {
    const sel = $("studio-collection");
    $("studio-db-status").textContent = "Loading collections…";
    try {
      const data = await req("/api/studio/database/collections");
      sel.replaceChildren(new Option("Choose collection", ""));
      data.collections.forEach(name => sel.add(new Option(name, name)));
      if (data.collections.includes(collection)) sel.value = collection;
      $("studio-db-status").textContent = `${data.collections.length} collections · read only`;
      if (collection) await loadRows();
    } catch (err) { $("studio-db-status").textContent = err.message; }
  }
  async function loadRows() {
    if (!collection) return;
    try {
      const data = await req(`/api/studio/database/collections/${encodeURIComponent(collection)}?limit=${pageSize}&skip=${page*pageSize}`);
      count = data.count;
      const table = $("studio-db-table"); table.replaceChildren();
      const keys = Array.from(new Set(data.rows.flatMap(item => Object.keys(item)))).slice(0, 12);
      const header = document.createElement("tr");
      keys.forEach(key => { const th = document.createElement("th");th.style.padding="10px";th.textContent=key;header.appendChild(th); });
      table.appendChild(header);
      data.rows.forEach(item => { const tr=document.createElement("tr");keys.forEach(key => td(tr,item[key]));table.appendChild(tr); });
      $("studio-db-status").textContent = `${collection}: ${count} rows · page ${page+1} · read only`;
      $("studio-db-prev").disabled = page===0;
      $("studio-db-next").disabled = (page+1)*pageSize >= count;
    } catch (err) { $("studio-db-status").textContent = err.message; }
  }
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
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelector('[data-view="database"]')?.addEventListener("click",loadCollections);
    document.querySelector('[data-view="social"]')?.addEventListener("click",loadDrafts);
    $("studio-db-toggle").addEventListener("click", () => {
      const el=$("studio-db-body");el.classList.toggle("hidden");
      $("studio-db-toggle").textContent=el.classList.contains("hidden")?"Show":"Hide";
    });
    $("studio-collection").addEventListener("change", e => {collection=e.target.value;page=0;loadRows();});
    $("studio-db-refresh").addEventListener("click",loadCollections);
    $("studio-db-prev").addEventListener("click",()=>{page=Math.max(0,page-1);loadRows();});
    $("studio-db-next").addEventListener("click",()=>{if((page+1)*pageSize<count){page++;loadRows();}});
    $("studio-social-form").addEventListener("submit",async e=>{
      e.preventDefault();
      const platforms=["instagram","facebook"].filter(x=>$("studio-social-"+x).checked);
      if(!platforms.length){$("studio-social-status").textContent="Choose at least one platform.";return;}
      const payload={title:$("studio-social-title").value.trim(),caption:$("studio-social-caption").value.trim(),image_url:$("studio-social-image").value.trim()||null,platforms};
      try{
        await req("/api/studio/social/drafts",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
        $("studio-social-status").textContent="Draft saved in MongoDB. Not published.";
        e.target.reset();await loadDrafts();
      }catch(err){$("studio-social-status").textContent=err.message;}
    });
  });
})();