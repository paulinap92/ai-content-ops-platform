import {createInspector,renderMonth} from "./inspector.js";
import {renderEditorialText} from "./editorialText.js";
const $ = (id) => document.getElementById(id);
const base = location.pathname.replace(/\/$/, "");
const state = {
  options: null,
  record: null,
  settings: null,
  offset: 0,
  total: 0,
  dirty: false,
  busy: false,
  recordsLoaded: false,
  target: {section:"home", resource:null},
  scope: "global",
};
const islandOrder = ["tenerife", "gran-canaria", "lanzarote", "fuerteventura", "la-palma", "la-gomera", "el-hierro", "la-graciosa"];
const guideLabels = {history:"Historia", climate:"Clima", "historical-weather":"Tiempo histórico", geology:"Geología", nature:"Naturaleza", experiences:"Planes", food:"Comida", culture:"Cultura", music:"Música", fiestas:"Fiestas", products:"Productos", crafts:"Artesanía", heritage:"Patrimonio", stories:"Historias"};
const guideGroups = {history:"Conoce la isla", geology:"Conoce la isla", climate:"Conoce la isla", "historical-weather":"Conoce la isla", nature:"Naturaleza", culture:"Cultura", heritage:"Cultura", music:"Cultura", fiestas:"Cultura", crafts:"Cultura", stories:"Cultura", food:"Sabores", products:"Sabores", experiences:"Experiencias"};
const resourceLabels = {...guideLabels, places:"Lugares", beaches:"Playas", "natural-pools":"Piscinas naturales", marinas:"Puertos deportivos", "food-producers":"Bodegas y queserías", "diving-spots":"Buceo", "leisure-centers":"Ocio", "museums-visits":"Museos y visitas", "natural-spaces":"Espacios naturales", "surf-spots":"Surf", stargazing:"Mirar las estrellas", markets:"Mercados", volcanoes:"Volcanes", summits:"Cumbres", routes:"Rutas", fauna:"Fauna", flora:"Flora", airports:"Aeropuertos",ports:"Puertos",ferries:"Ferries", "titsa-stops":"TITSA · paradas", "titsa-routes":"TITSA · líneas", "tilp-routes":"TILP · La Palma",coastal:"Mar y mareas",featured:"Destacados",news:"Noticias",weather:"Tiempo", "air-quality":"Calidad del aire",marine:"Mar",tides:"Mareas",alerts:"Avisos",seismic:"Sismos",volcanic:"Volcanes",webcams:"Webcams",tourism:"Turismo",population:"Población",economy:"Economía",housing:"Vivienda",environment:"Medio ambiente"};
const islandDescriptions = {
 "tenerife":"Hola, soy Tenerife. Tengo volcanes, bosques, playas y el pico más alto de España.",
 "gran-canaria":"Hola, soy Gran Canaria. Tengo barrancos, pueblos de montaña y dunas junto al Atlántico.",
 "lanzarote":"Hola, soy Lanzarote. Soy volcánica, árida y a veces parezco de otro planeta.",
 "fuerteventura":"Hola, soy Fuerteventura. Tengo playas infinitas, viento y paisajes casi desérticos.",
 "la-palma":"Hola, soy La Palma. Soy verde, abrupta y me gusta mirar las estrellas.",
 "la-gomera":"Hola, soy La Gomera. Tengo laurisilva, barrancos profundos y pueblos tranquilos.",
 "el-hierro":"Hola, soy El Hierro. Soy pequeña, volcánica, remota y voy a otro ritmo.",
 "la-graciosa":"Hola, soy La Graciosa. No tengo asfalto, pero sí arena clara, mar y mucha calma."
};
function statusLabel(item) {
 if(item.draft?.hidden) return "Wpis ukryty";
 return ({published:"Opublikowane", draft:"Wersja robocza", new:"Nowy szkic"})[item.status] || item.status;
}
function resourceLabel(key) { return resourceLabels[key] || String(key).replaceAll("-", " "); }
const inspection=createInspector({root:document.getElementById("inspection-view"),api,label:key=>islandOrder.includes(key)?islandName(key):resourceLabel(key),onIsland:(island,section,resource)=>task(()=>navigate(section,resource,island))});
const labels = {
  name: "Nazwa",
  title: "Tytuł",
  slug: "Adres wpisu (slug)",
  description: "Treść / opis",
  short_description: "Krótki opis",
  summary: "Streszczenie",
  category: "Kategoria",
  tags: "Tagi",
  latitude: "Szerokość geograficzna",
  longitude: "Długość geograficzna",
  geometry: "Geometria GeoJSON (trasy i obszary)",
  image_url: "Adres zdjęcia",
  image_alt: "Opis alternatywny zdjęcia",
  image_credit: "Autor / prawa do zdjęcia",
  image_source_url: "Źródło zdjęcia",
  source_url: "Źródło informacji",
  url: "Adres strony",
  website: "Strona internetowa",
  featured: "Wyróżnione",
  order: "Kolejność",
  hidden: "Ukryj wpis na stronie",
  start_date: "Data początku",
  end_date: "Data końca",
  all_day: "Cały dzień",
  location: "Miejsce",
  venue: "Obiekt",
  price: "Cena",
  language: "Język główny",
  translations: "Wersje językowe",
  editor_notes: "Prywatne notatki redakcyjne",
};
const protectedKeys = new Set([
  "id",
  "canonical_id",
  "canonical_slug",
  "entity_type",
  "catalog_code",
  "island",
  "source_id",
  "route_id",
  "osm_id",
  "osm_type",
  "gbif_id",
  "editorial_override",
  "geometry_override",
  "source_updated_at",
  "ingested_at",
  "created_at",
  "updated_at",
]);
function node(tag, text, attributes = {}) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  for (const [k, v] of Object.entries(attributes)) e.setAttribute(k, v);
  return e;
}
function message(text, error = false) {
  const feedback=document.getElementById("record-feedback");if(feedback){feedback.textContent=text;feedback.className=error?"inspection-error":"view-help";}
  $("status").textContent = text;
  $("status").classList.toggle("error", error);
}
function islandName(slug) {
  if (slug === "canarias") return "Całe Wyspy Kanaryjskie";
  return slug
    .split("-")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}
async function api(path, options = {}) {
  const r = await fetch(`${base}/api${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
    cache: "no-store",
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 401) {
      window.top.location.assign("/login");
    }
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail || `Błąd ${r.status}`),
    );
  }
  return data;
}
async function task(action) {
  if (state.busy) return;
  state.busy = true;
  document
    .querySelectorAll(".actions button")
    .forEach((b) => (b.disabled = true));
  try {
    await action();
  } catch (e) {
    message(e.message, true);
  } finally {
    state.busy = false;
    document
      .querySelectorAll(".actions button")
      .forEach((b) => (b.disabled = false));
  }
}
function params() {
  return {
    kind: $("kind").value,
    island: $("island").value,
    resource:
      $("kind").value === "calendar" ? $("month").value : $("resource").value,
  };
}
function warnUnsaved() {
  return !state.dirty || confirm("Masz niezapisane poprawki. Opuścić wpis?");
}
function resources() {
  const kind = $("kind").value;
  const selectedIsland = $("island").value;
  const ordered = islandOrder.filter(v => state.options.islands.includes(v));
  const choices = kind === "news" ? ["canarias", ...ordered] : ordered;
  $("island").replaceChildren(...choices.map((v) => new Option(islandName(v), v)));
  if (choices.includes(selectedIsland)) $("island").value = selectedIsland;
  const values =
    kind === "guide"
      ? Object.keys(guideLabels).filter(v => state.options.features.guide.includes(v))
      : kind === "explore"
        ? state.options.features.explore.filter(
            (x) =>
              ![
                "airports",
                "ports",
                "ferries",
                "titsa-stops",
                "titsa-routes",
                "tilp-routes",
              ].includes(x),
          )
        : kind === "live-point" ? ["weather","air-quality","coastal"] : kind === "news"
          ? ["news"]
          : [];
  $("resource").replaceChildren(
    ...values.map((v) => new Option(resourceLabel(v), v)),
  );
  $("resource").hidden = kind === "calendar";
  $("month").hidden = kind !== "calendar";
}
async function loadRecords() {
  const {kind,island,resource} = params();
  const section = state.target.section === "explore" && state.target.resource === "featured" ? "Explore → Destacados" : ({guide:"Guía", explore:"Explore", calendar:"Calendario", news:"Noticias"})[kind];
  $("content-location").textContent = [islandName(island), section, kind === "guide" ? guideGroups[resource] : null, kind === "calendar" ? resource : resourceLabel(resource)].filter(Boolean).join(" → ");
  message("Wczytuję treści wybranej wyspy i kategorii…");
  state.offset = state.offset || 0;
  let result = await api(
    "/records?" +
      new URLSearchParams({
        ...params(),
        q: $("search").value,
        offset: state.offset,
        limit: 100,
      }),
  );
  if(kind === "calendar") {
    const items=[...result.items];
    while(items.length<result.count && items.length<2000) {const page=await api("/records?"+new URLSearchParams({...params(),q:$("search").value,offset:items.length,limit:100}));if(!page.items.length)break;items.push(...page.items);}
    items.sort((a,b)=>String(a.draft.start_date||"9999").localeCompare(String(b.draft.start_date||"9999")) || String(a.draft.title||"").localeCompare(String(b.draft.title||"")));
    for(const [id,key] of [["calendar-town","location"],["calendar-category","category"]]){
      const select=$(id),previous=select.value;select.replaceChildren(new Option("Wszystkie",""),...[...new Set(items.map(i=>String(key==='location'?(i.draft.municipality||i.draft.city||i.draft.location||i.draft.venue||''):(i.draft.category||''))).filter(Boolean))].sort().map(v=>new Option(v,v)));if([...select.options].some(o=>o.value===previous))select.value=previous;
    }
    const filtered=items.filter(i=>{const p=i.draft,town=String(p.municipality||p.city||p.location||p.venue||''),from=$("calendar-from").value,to=$("calendar-to").value,status=$("calendar-state").value;return (!$("calendar-town").value||town===$("calendar-town").value)&&(!$("calendar-category").value||p.category===$("calendar-category").value)&&(!from||String(p.end_date||p.start_date)>=from)&&(!to||String(p.start_date)<=to)&&(!status||(status==='hidden'?p.hidden:status==='draft'?i.status==='draft'||i.status==='new':i.status==='published'&&!p.hidden));});
    result={...result,items:filtered,count:filtered.length};
    items.splice(0,items.length,...filtered);
    renderMonth($("calendar-grid"),items,resource,item=>{state.record=item;renderRecord();$("editor-title").scrollIntoView({behavior:"smooth",block:"start"});});
    $("calendar-available-months").replaceChildren();
    if(!items.length){try{const data=await inspection.getCoverage();const months=data.calendar.filter(r=>r.island===island&&r.count>0).slice(0,6);if(months.length){$("calendar-available-months").append(node("span","Miesiące z wydarzeniami: "));for(const row of months){const b=node("button",`${row.month} · ${row.count}`,{type:"button"});b.onclick=()=>task(async()=>{$("month").value=row.month;state.offset=0;await loadRecords();});$("calendar-available-months").append(b);}}}catch(_){/* Current-month empty state and month controls stay usable. */}}

  }
  state.total = result.count;
  $("record-list").replaceChildren();
  for (const item of result.items) {
    const b = node(
      "button",
      (kind === "calendar" ? `${item.draft.start_date||"Bez daty"} · ` : "") + (item.draft.name || item.draft.title || item.identity.record_key),
      { class: "record" },
    );
    b.append(
      node(
        "small",
        `${statusLabel(item)} · wersja ${item.version}${item.draft.hidden ? " · ukryte" : ""}`,
      ),
    );
    b.onclick = () => {
      if (!warnUnsaved()) return;
      state.record = item;
      renderRecord();
      document.querySelectorAll(".record").forEach(e => e.classList.toggle("active", e === b));
    };
    $("record-list").append(b);
  }
  const selected = result.items.find(item => item.identity.record_key === state.record?.identity.record_key) || result.items.find(item => item.identity.record_key === state.requestedKey) || result.items[0];
  state.requestedKey=null;
  if(selected && !state.dirty) {state.record = selected;renderRecord();}
  if(!selected && !state.dirty) {state.record=null;$("record-form").replaceChildren();$("edit-actions").hidden=true;$("editor-title").textContent="Brak treści w tej części strony";$("published-record-preview").replaceChildren();}
  if (!result.items.length) $("record-list").append(node("p", "Brak wpisów dla wybranej wyspy, kategorii i wyszukiwania. Wybierz inną kategorię lub usuń tekst wyszukiwania.", {class:"empty-state"}));
  if(!result.items.length && ["guide","explore"].includes(kind)) {
    try {$("record-list").append(await inspection.emptyHint(state.target.section,state.target.resource,island));}catch(_){/* The main empty state remains accurate if optional coverage is unavailable. */}
  }
  state.recordsLoaded = true;
  $("page").textContent =
    `${result.count ? state.offset + 1 : 0}–${state.offset + result.items.length} / ${result.count}`;
  $("prev").disabled = kind === "calendar" || state.offset === 0;
  $("next").disabled = kind === "calendar" || state.offset + 100 >= state.total;
  message(result.count?`Wczytano wpisów: ${result.count}. Wybrana treść jest otwarta do edycji.`:"Brak wpisów w wybranej części strony.");
}
function field(key, value, readonly = false) {
  const label = node("label", labels[key] || key);
  const object = value !== null && typeof value === "object";
  const long =
    object ||
    [
      "description",
      "short_description",
      "summary",
      "body_markdown",
      "editor_notes",
    ].includes(key) ||
    String(value || "").length > 160;
  const input = node(long ? "textarea" : "input");
  input.dataset.key = key;
  input.dataset.valueType = object ? "json" : typeof value;
  input.dataset.null = String(value === null);
  if (typeof value === "boolean") {
    input.type = "checkbox";
    input.checked = value;
  } else {
    if (input.tagName === "INPUT")
      input.type =
        typeof value === "number" || ["latitude", "longitude", "order"].includes(key)
          ? "number"
          : key.endsWith("url") || key === "website"
            ? "url"
            : "text";
    if (input.type === "number") input.step = "any";
    input.value = object ? JSON.stringify(value, null, 2) : (value ?? "");
  }
  input.readOnly = readonly;
  input.oninput = () => {
    state.dirty = true;
    $("record-status").textContent = "Niezapisane zmiany";
  };
  label.append(input);
  if (long) label.className = "wide";
  return label;
}
function renderRecord() {
  const item = state.record;
  state.dirty = false;
  $("history-list").replaceChildren();
  $("editor-title").textContent =
    item.draft.name || item.draft.title || "Nowy wpis";
  $("record-status").textContent =
    `${statusLabel(item)} · wersja ${item.version}. Zapis roboczy nie zmienia strony.`;
  const preview = $("published-record-preview");
  preview.replaceChildren(node("h3",item.published?.name || item.published?.title || "Jeszcze nieopublikowane"));
  const body=node("div");body.innerHTML=renderEditorialText(item.published?.description || item.published?.summary || "");preview.append(body);
  const fields = node("div", undefined, { class: "fields" });
  const advanced = node("details");
  advanced.append(node("summary", "Dodatkowe pola i dane strukturalne"));
  const keys = new Set([
    ...["name", "title", "short_description", "summary", "description"].filter(key => Object.hasOwn(item.draft,key)),
    ...Object.keys(item.draft),
    "image_url",
    "image_alt",
    "image_credit",
    "image_source_url",
    "source_url",
    "hidden",
    "editor_notes",
  ]);
  for (const key of keys) {
    if (key.startsWith("_") || protectedKeys.has(key)) continue;
    const value = Object.hasOwn(item.draft, key) ? item.draft[key] : (key === "hidden" ? false : key === "editor_notes" ? [] : "");
    (Object.hasOwn(labels, key) ? fields : advanced).append(
      field(
        key,
        value,
        key === "slug" && !item.identity.record_key.startsWith("new:"),
      ),
    );
  }
  $("record-form").replaceChildren(fields, advanced);
  $("edit-actions").hidden = false;
  $("publish").disabled = !item.id;
  $("publish").textContent=item.identity.kind==="calendar"?"Opublikuj wydarzenie":item.identity.kind==="live-point"?"Włącz punkt w jobach Live":"Opublikuj treść";
  $("improve-ai").hidden=item.identity.kind!=="guide";
}
function recordPayload() {
  const value = structuredClone(state.record.draft);
  for (const input of $("record-form").querySelectorAll("[data-key]")) {
    let v = input.type === "checkbox" ? input.checked : input.value;
    if (input.dataset.valueType === "json") {
      try {
        v = JSON.parse(v);
      } catch {
        throw new Error(
          `${input.dataset.key}: nieprawidłowa lista lub obiekt.`,
        );
      }
    } else if (input.type === "number")
      v = input.value === "" ? null : Number(v);
    else if (input.value === "" && input.dataset.null === "true") v = null;
    value[input.dataset.key] = v;
  }
  return value;
}
async function digest(value) {
  const sorted = (v) =>
    Array.isArray(v)
      ? v.map(sorted)
      : v && typeof v === "object"
        ? Object.fromEntries(
            Object.keys(v)
              .sort()
              .map((k) => [k, sorted(v[k])]),
          )
        : v;
  const bytes = new TextEncoder().encode(JSON.stringify(sorted(value)));
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("");
}
async function save(which) {
  if (which === "settings") collectSettings();
  const item = state[which];
  const payload = which === "record" ? recordPayload() : item.draft;
  state[which] = await api("/draft", {
    method: "PUT",
    body: JSON.stringify({
      identity: item.identity,
      payload,
      expected_version: item.version,
      base_fingerprint: item.base_fingerprint,
    }),
  });
  state.dirty = false;
  if (which === "settings") state.settingsDirty=false;
  message("Zapisano wersję roboczą. Strona pozostaje bez zmian.");
  if (which === "record") {
    renderRecord();
    await loadRecords();
  } else {
    state.settings.savedFingerprint = await digest(state.settings.draft);
    renderSettings();
  }
}
async function publish(which) {
  if (state.dirty && which === "record")
    throw new Error("Najpierw zapisz wersję roboczą.");
  if (which === "settings") {
    collectSettings();
    if (
      (await digest(state.settings.draft)) !== state.settings.savedFingerprint
    )
      throw new Error("Najpierw zapisz ustawienia robocze.");
  }
  const item = state[which];
  if (!item?.id) throw new Error("Najpierw zapisz wersję roboczą.");
  preview(which);
  if (
    !confirm(
      which === "settings"
        ? "Opublikować zapisany szkic tekstów i widoczności? Obejmuje wszystkie zapisane zmiany ustawień strony, także z innych sekcji i wysp. Sprawdź podgląd różnic."
        : "Opublikować tę wersję na stronie?",
    )
  )
    return;
  state[which] = await api(`/documents/${item.id}/publish`, {
    method: "POST",
    body: JSON.stringify({ expected_version: item.version }),
  });
  $("preview-dialog").close();
  message(
    "Opublikowano. Strona pobierze zmianę przy odświeżeniu; ustawienia aktualizują się także w otwartych kartach.",
  );
  if (which === "record") {
    renderRecord();
    await loadRecords();
  } else {
    state.settings.savedFingerprint = await digest(state.settings.draft);
    renderSettings();
  }
}
function preview(which) {
  if (which === "settings") collectSettings();
  const item = state[which],
    draft = which === "record" ? recordPayload() : item.draft;
  const root = $("preview-content");
  root.replaceChildren();
  if (which === "record") {
    root.append(
      node("h2", draft.name || draft.title),
      node("p", draft.short_description || draft.summary || ""),
    );
    if (/^https?:\/\//.test(draft.image_url || ""))
      root.append(
        node("img", undefined, {
          src: draft.image_url,
          alt: draft.name || draft.title || "",
        }),
      );
    const body=node("div");body.innerHTML=renderEditorialText(draft.description || "");root.append(body);
    if (draft.hidden)
      root.append(node("strong", "Ten wpis będzie ukryty na stronie."));
  } else root.append(node("h2", "Podgląd ustawień"));
  const changes = $("change-list");
  changes.replaceChildren();
  function diff(before, after, prefix = "") {
    const keys = new Set([
      ...Object.keys(before || {}),
      ...Object.keys(after || {}),
    ]);
    for (const key of keys) {
      const a = before?.[key],
        b = after?.[key],
        path = prefix ? `${prefix}.${key}` : key;
      if (
        a &&
        b &&
        !Array.isArray(a) &&
        !Array.isArray(b) &&
        typeof a === "object" &&
        typeof b === "object"
      ) {
        diff(a, b, path);
        continue;
      }
      if (JSON.stringify(a) === JSON.stringify(b)) continue;
      const block = node("div", undefined, { class: "change" });
      block.append(
        node("strong", labels[path] || path),
        node(
          "pre",
          `Było: ${JSON.stringify(a) ?? "brak"}\nBędzie: ${JSON.stringify(b) ?? "brak"}`,
        ),
      );
      changes.append(block);
    }
  }
  diff(item.published || {}, draft);
  if (!changes.childNodes.length) changes.append(node("p", "Brak różnic."));
  if (!$("preview-dialog").open) $("preview-dialog").showModal();
}
async function showHistory(which) {
  const item = state[which];
  if (!item) throw new Error("Najpierw wybierz treść.");
  const root=$("history-dialog-content");
  if(!item.id){root.replaceChildren(node("h2","Historia tej treści"),node("p","Ten wpis pochodzi z opublikowanej bazy i nie był jeszcze edytowany w Studio. Zapis pierwszego szkicu zachowa obecną treść jako wersję 0. Starszych zmian sprzed uruchomienia historii nie ma w Studio."));if(!$("history-dialog").open)$("history-dialog").showModal();return;}
  const data = await api(`/documents/${item.id}/history`);
  root.replaceChildren(
    node("h3", "Historia — przywrócenie tworzy wersję roboczą"),
  );
  if(!data.items.length)root.append(node("p","Brak zapisanych wersji."));
  if(!$("history-dialog").open)$("history-dialog").showModal();
  for (const revision of data.items) {
    const b = node(
      "button",
      `Wersja ${revision.version} · ${revision.action} · ${new Date(revision.created_at).toLocaleString("pl")}`,
    );
    b.onclick = () =>
      task(async () => {
        if (!warnUnsaved()) return;
        state[which] = await api(`/documents/${item.id}/restore`, {
          method: "POST",
          body: JSON.stringify({
            version: revision.version,
            expected_version: state[which].version,
          }),
        });
        state.dirty = false;
        if (which === "settings")
          state.settings.savedFingerprint = await digest(state.settings.draft);
        which === "record" ? renderRecord() : renderSettings();
        $("history-dialog").close();
        message(
          "Przywrócono do wersji roboczej. Możesz ją obejrzeć i opublikować.",
        );
      });
    root.append(b);
  }
}
function scopeSettings() {
  const config = state.settings.draft;
  if (state.scope === "global") return config.global;
  return (config.islands[state.scope] ?? {
    sections: {},
    features: {},
    copy: {},
  });
}
function retainScope(scope) {
  if(state.scope !== "global" && ["sections","features","copy"].some(key => Object.keys(scope[key]).length)) state.settings.draft.islands[state.scope] = scope;
}
function markSettingsDirty() {state.settingsDirty=true;$("settings-state").textContent="Niezapisane zmiany — zapisz szkic przed publikacją.";}
function collectSettings() {
  if (!state.settings) return;
  const scope = scopeSettings();
  for (const select of $("settings-form").querySelectorAll("[data-setting]")) {
    const values = (scope[select.dataset.setting] ??= {});
    if (select.value === "inherit") delete values[select.dataset.key];
    else values[select.dataset.key] = select.value === "true";
  }
  for (const row of $("settings-form").querySelectorAll("[data-copy]")) {
    const key = row.dataset.copy;
    if (row.querySelector('input[type="checkbox"]').checked)
      scope.copy[key] = row.querySelector("textarea").value;
    else delete scope.copy[key];
  }
  retainScope(scope);
}
async function loadSettings() {
  const data = await api(
    "/records?" +
      new URLSearchParams({
        kind: "settings",
        island: "global",
        resource: "site",
      }),
  );
  state.settings = data.items[0];
  state.settings.savedFingerprint = await digest(state.settings.draft);
  renderSettings();
}
function renderSettings() {
  const scope = scopeSettings(),
    root = $("settings-form");
  root.replaceChildren();
  const groups = new Map();
  const textGroup = key => key.startsWith("home.") || key.startsWith("island.") ? "Strona startowa i opis wyspy" : key.startsWith("nav.") ? "Menu główne" : key.startsWith("feature.") ? (state.options.sections[key.split(".")[1]] || "Pozostałe teksty") : (state.options.sections[key.split(".")[0]] || "Pozostałe teksty");
  const keys = { ...state.options.copy_defaults };
  for (const [area, items] of Object.entries(state.options.features))
    for (const key of items) {
      keys[`feature.${area}.${key}.title`] ??= key;
      keys[`feature.${area}.${key}.description`] ??= "";
    }
  const {section,resource}=state.target;
  const inContext = key => section === "home" ? (state.scope === "global" ? key.startsWith("home.") : key === "island.description") : resource ? key.startsWith(`feature.${section}.${resource}.`) : key === `nav.${section}` || key.startsWith(`${section}.`);
  for (const [key, fallback] of Object.entries(keys).filter(([key]) => inContext(key))) {
    const groupName = textGroup(key);
    if(!groups.has(groupName)) {
      const detail = node("details",undefined,{class:"copy-group"});
      detail.open = true;
      detail.append(node("summary",groupName));
      const body = node("div");detail.append(body);root.append(detail);groups.set(groupName,body);
    }
    const body = groups.get(groupName);
    const row = node("div", undefined, { "data-copy": key });
    const label = node("label", copyLabel(key, keys)),
      toggle = node("input", undefined, { type: "checkbox" });
    toggle.checked = Object.hasOwn(scope.copy, key);
    const check = node("label", "Własny tekst", { class: "copy-override" });
    check.prepend(toggle);
    const input = node("textarea", undefined, {
      placeholder: fallback,
      rows: "2",
    });
    const effectiveDefault = key === "island.description" && state.scope !== "global" ? islandDescriptions[state.scope] || fallback : fallback;
    input.value = scope.copy[key] ?? state.settings.draft.global.copy[key] ?? effectiveDefault;
    const published = state.settings.published || {global:{copy:{}},islands:{}};
    const publishedValue = (state.scope === "global" ? published.global : published.islands?.[state.scope])?.copy?.[key] ?? published.global?.copy?.[key] ?? effectiveDefault;
    if(input.value !== publishedValue) row.append(node("small", "Obecnie na stronie: " + (publishedValue || "(pusty tekst)"), {class:"published-copy"}));
    if(key === "island.description" && state.scope === "global") row.append(node("small", "Każda wyspa ma swój opis. Wybierz ją w polu Zakres zmiany, aby zobaczyć i edytować ten tekst.", {class:"muted"}));
    input.oninput = () => { toggle.checked = true; markSettingsDirty(); };
    toggle.onchange = () => { markSettingsDirty(); };
    label.append(input);
    row.append(label, check);
    body.append(row);
  }
  renderContextVisibility();
  $("settings-state").textContent =
    `${state.settingsDirty ? "Niezapisane zmiany · " : ""}${statusLabel(state.settings)} · wersja ${state.settings.version}. Publikacja obejmuje zapisany szkic tekstów i widoczności całej strony.`;
}
function copyLabel(key, defaults) {
  const direct = {"home.title":"Nagłówek strony startowej", "home.description":"Opis strony startowej", "island.description":"Opis wyspy", "guide.title":"Nagłówek Guide", "guide.description":"Opis Guide", "datos.title":"Nagłówek Datos", "datos.description":"Opis Datos"};
  if (direct[key]) return direct[key];
  if (key.startsWith("nav.")) return "Nazwa sekcji: " + state.options.sections[key.slice(4)];
  const prefix=key.slice(0,key.lastIndexOf("."));
  const name=defaults[prefix+".title"]||prefix.split(".").slice(1).join(" / ");
  return (key.endsWith(".description")?"Opis: ":key.endsWith(".subtitle")?"Podtytuł: ":"Nazwa: ")+name;
}
async function loadMedia() {
  const data = await api(
    "/media?" + new URLSearchParams({ island: $("media-island").value }),
  );
  $("upload").disabled = !data.upload_enabled || $("media-island").value==="global";
  $("media-status").textContent = $("media-island").value==="global" ? "Wybierz wyspę zdjęcia, aby przesłać nowy plik. Poniżej widzisz całą bibliotekę." : data.upload_enabled
    ? "Zdjęcia są przechowywane trwale. Przesłany plik będzie dostępny publicznie pod swoim adresem; artykuł lub wydarzenie opublikujesz osobno. Zdjęcia z telefonu zmniejszamy przed wysłaniem."
    : "Wgrywanie wymaga konfiguracji R2. W edytorze możesz podać istniejący URL zdjęcia.";
  $("media-list").replaceChildren();
  for (const image of data.items) {
    const b = node("button", image.filename);
    b.prepend(node("img", undefined, { src: image.url, alt: image.filename }));
    b.onclick = () => {
      if (!state.record) {
        if(parent!==window){parent.postMessage({type:"cc-editor-image",image},location.origin);message("Wybieram zdjęcie do otwartej treści…");}
        else navigator.clipboard.writeText(image.url).then(()=>message("Skopiowano adres zdjęcia. Wklej go w wybranym wpisie w polu Adres zdjęcia."),()=>message(image.url));
        return;
      }
      state.record.draft = state.record ? recordPayload() : {};
      state.record.draft.image_url = image.url;
      state.record.draft.image_alt = image.alt || image.filename;
      state.record.draft.image_credit = image.credit || "";
      renderRecord();
      state.dirty = true;
      view("content");
      message("Zdjęcie przypisano do formularza. Zapisz wersję roboczą.");
    };
    $("media-list").append(b);
  }
}
function view(name) {
  inspection.cancel();
  $("inspection-view").hidden = name !== "inspection";
  $("calendar-view").hidden = name !== "content" || params().kind !== "calendar";
  $("content-view").hidden = name !== "content";
  const noSettings=["media","database","coverage","live-points","transport"].includes(state.target.section);
  $("settings-view").hidden = noSettings;
  $("context-settings").hidden = noSettings;
  $("context-settings").open = name === "settings";
  $("media-view").hidden = name !== "media";
  $("save-settings").parentElement.hidden = noSettings;
  $("settings-state").hidden = noSettings;
}
function contextSetting() {
  const {section,resource}=state.target;
  return ["home","media","database","coverage","transport","live-points"].includes(section) || section === "explore" && resource === "featured" ? null : {kind:resource?"features":"sections",key:resource?`${section}.${resource}`:section};
}
function renderContextVisibility() {
  const root=$("context-visibility");root.replaceChildren();
  const setting=contextSetting();if(!setting)return;
  const scope=scopeSettings(), values=scope[setting.kind] ||= {};
  const inherited=state.settings.draft.global[setting.kind]?.[setting.key] ?? true;
  const enabled=values[setting.key] ?? inherited;
  const parentHidden=setting.kind === "features" && (scope.sections[state.target.section] ?? state.settings.draft.global.sections[state.target.section] ?? true) === false;
  const switchText=enabled?(parentHidden?"Podsekcja włączona, sekcja ukryta":"Widoczna na stronie"):"Ukryta na stronie";
  const toggle=node("button", switchText,{role:"switch","aria-checked":String(enabled),class:"visibility-switch",type:"button"});
  toggle.onclick=()=>{collectSettings();const current=scopeSettings();current[setting.kind][setting.key]=!enabled;retainScope(current);markSettingsDirty();renderContextVisibility();renderTree();};
  root.append(toggle);
  if(setting.kind === "features") {
    const parentKey=state.target.section;
    if((scope.sections[parentKey] ?? state.settings.draft.global.sections[parentKey] ?? true) === false) root.append(node("small",`Cała sekcja ${state.options.sections[parentKey]} jest ukryta. Włącz ją w drzewie, aby pokazać tę podsekcję.`,{class:"parent-visibility-note"}));
  }
  if(state.scope!=="global" && Object.hasOwn(values,setting.key)){
    const reset=node("button","Jak na całej stronie",{class:"inherit-reset",type:"button"});
    reset.onclick=()=>{collectSettings();const current=scopeSettings();delete current[setting.kind][setting.key];retainScope(current);markSettingsDirty();renderContextVisibility();renderTree();};root.append(reset);
  }
}
function renderTree(){
 const root=$("site-tree");root.replaceChildren();
 function add(section,resource,label,child=false){
  const active=state.target.section===section && state.target.resource===(resource||null);
  const b=node("button",label,{type:"button",class:child?"tree-child":"tree-section","aria-current":active?"page":"false"});
  b.onclick=()=>task(()=>navigate(section,resource||null));root.append(b);
 }
 add("home",null,state.scope==="global"?"Strona startowa":"Opis wyspy");
 for(const [section,label] of Object.entries(state.options.sections)){
  add(section,null,label);
  if(state.target.section!==section)continue;
  const values=section==="guide"?Object.keys(guideLabels).filter(v=>state.options.features.guide.includes(v)):section==="explore"?["featured",...(state.options.features.explore||[])]:state.options.features[section]||[];
  for(const resource of values){

   add(section,resource,resourceLabel(resource),true);
  }
 }
 add("transport",null,"Transporte");
 if(state.target.section==="transport")for(const r of ["airports","ports","ferries","titsa-stops","titsa-routes","tilp-routes"])add("transport",r,resourceLabel(r),true);
 add("live-points",null,"Własne punkty Live");
 if(state.target.section==="live-points")for(const r of ["weather","air-quality","coastal"])add("live-points",r,resourceLabel(r),true);
 add("media",null,"Zdjęcia");
 add("coverage",null,"Kompletność danych");
 add("database",null,"Baza danych");
}
async function navigate(section,resource=null,nextScope=state.scope){
 if(!warnUnsaved()){$("tree-scope").value=state.scope;return;}
 collectSettings();
 if(section === "calendar" && resource) $("month").value = resource;
 if(section === "calendar" || section === "news") resource = null;
 state.scope=nextScope === "canarias" && section === "news" ? "global" : nextScope;
 if(section==="transport")resource ||= "airports";
 if(section==="live-points")resource ||= "weather";
 state.target={section,resource};
 const transport=section==="transport" || section==="explore" && ["airports","ports","ferries","titsa-stops","titsa-routes","tilp-routes"].includes(resource);
 const editable=!transport && ["guide","explore","calendar","news","live-points"].includes(section) && (resource || section==="calendar" || section==="news");
 $("scope").value=state.scope;$("tree-scope").value=state.scope;
 $("context-path").textContent=section==="database"?"Cała baza strony":section==="coverage"?"Wszystkie wyspy":state.scope==="global"?"Cała strona":islandName(state.scope);
 $("context-title").textContent=section==="home"?(state.scope==="global"?"Strona startowa":"Opis wyspy"):section==="media"?"Zdjęcia":section==="database"?"Baza danych":section==="coverage"?"Kompletność danych":[section==="transport"?"Transporte":section==="live-points"?"Własne punkty Live":state.options.sections[section],resource?resourceLabel(resource):null].filter(Boolean).join(" / ");
 $("context-help").textContent=section==="database"?"Przeglądaj rzeczywistą bazę PostgreSQL: tabele, kolumny i rekordy. Ten widok jest tylko do odczytu.":section==="coverage"?"Zestawienie rzeczywistych danych według katalogu i wyspy; puste źródła są pokazane wprost.":editable?"Po lewej wybierz wpis. Otwieramy pierwszy automatycznie; możesz porównać go z opublikowaną wersją poniżej formularza.":["live","datos"].includes(section)?"Tutaj zmieniasz teksty i widoczność tej części. Pomiary i wykresy są aktualizowane przez joby, a nie ręcznie.":"Edytuj teksty widoczne na stronie. Zapis roboczy zachowuje szkic; publikacja udostępnia zmiany odwiedzającym.";
 renderTree();renderSettings();
 $("island").value=state.scope==="global"?"tenerife":state.scope;
 if(section==="database"){view("inspection");await inspection.showDatabase();return;}
 if(section==="coverage"){view("inspection");await inspection.showCoverage();return;}
 if(section==="media"){if(state.scope!=="global")$("media-island").value=state.scope;view("media");await loadMedia();return;}
 if(section==="live"||section==="datos"||transport){view("inspection");await inspection.showData(transport?"explore":section,resource||(section==="live"?"weather":"climate"),state.scope);return;}
 if(editable && state.scope==="global" && section==="live-points"){view("inspection");$("inspection-view").append(node("h2","Własne punkty Live"),node("p","Wybierz wyspę po lewej. Dodaj punkt, zapisz szkic, a następnie włącz go w jobach. Pomiary pojawią się po udanym odświeżeniu źródła, zgodnie z harmonogramem danego źródła. Wyłączenie punktu zachowuje jego historię."));return;}
 if(editable && state.scope==="global" && section!=="news"){view("inspection");await inspection.showCoverage(section,resource);return;}
 if(editable){
  $("kind").value=section==="live-points"?"live-point":section === "explore" && resource === "featured" ? "guide" : section;resources();
  if(section === "explore" && resource === "featured") $("resource").append(new Option("Destacados","explore"));
  $("island").value=section === "news" && state.scope === "global" ? "canarias" : state.scope;
  if(resource)$("resource").value=section === "explore" && resource === "featured" ? "explore" : resource;
  $("calendar-month-control").hidden=section!=="calendar";
  $("month").hidden=section!=="calendar";
  $("resource-label").hidden=true;
  if(section==="calendar")$("calendar-month-control").append($("month"));
  state.offset=0;state.record=null;state.dirty=false;$("search").value="";
  view("content");await loadRecords();
 }else {view("settings");message("Wczytano wybraną część strony. Zmiany czekają na zapis i publikację.");}
}
async function init() {
  state.options = await api("/options");
  $("workspace").hidden = false;
  $("logout").hidden = false;
  $("island").replaceChildren(
    ...islandOrder.filter(v => state.options.islands.includes(v)).map((v) => new Option(islandName(v), v)),
  );
  $("scope").replaceChildren(
    new Option("Cała strona", "global"),
    ...islandOrder.filter(v => state.options.islands.includes(v)).map((v) => new Option(islandName(v), v)),
  );
  const requested = new URLSearchParams(location.search);state.requestedKey=requested.get("record_key");
  if (["guide", "explore", "calendar", "news"].includes(requested.get("kind")))
    $("kind").value = requested.get("kind");
  $("month").value = /^\d{4}-(0[1-9]|1[0-2])$/.test(
    requested.get("resource") || "",
  )
    ? requested.get("resource")
    : new Date().toISOString().slice(0, 7);
  $("island").value = "tenerife";
  resources();
  if ([...$("island").options].some((v) => v.value === requested.get("island")))
    $("island").value = requested.get("island");
  if (
    [...$("resource").options].some(
      (x) => x.value === requested.get("resource"),
    )
  )
    $("resource").value = requested.get("resource");
  $("media-island").replaceChildren(new Option("Wszystkie wyspy","global"),...islandOrder.map(v=>new Option(islandName(v),v)));
  $("media-island").onchange=()=>task(loadMedia);
  $("tree-scope").replaceChildren(new Option("Cała strona","global"),...islandOrder.filter(v=>state.options.islands.includes(v)).map(v=>new Option(islandName(v),v)));
  $("tree-scope").onchange=()=>task(()=>navigate(state.target.section,state.target.resource,$("tree-scope").value));
  await loadSettings();
  if(["database","coverage","media"].includes(requested.get("view"))) await navigate(requested.get("view"));
  else if(["transport","live-points"].includes(requested.get("section"))) await navigate(requested.get("section"),requested.get("resource"),islandOrder.includes(requested.get("island"))?requested.get("island"):"global");
  else if(Object.hasOwn(state.options.sections,requested.get("section")) && (!requested.get("resource") || state.options.features[requested.get("section")]?.includes(requested.get("resource")) || requested.get("section")==="explore" && requested.get("resource")==="featured")) await navigate(requested.get("section"),requested.get("resource"),islandOrder.includes(requested.get("island"))?requested.get("island"):"global");
  else if(requested.has("kind")) {const p=params();await navigate(p.kind,p.resource,p.island);}
  else await navigate("home");
  parent.postMessage({type:"cc-editor-ready"},location.origin);
}
for (const key of ["island", "kind", "resource", "month"]) {
  $(key).onchange = () =>
    task(async () => {
      if (!warnUnsaved()) return;
      if (key === "kind") resources();
      state.offset = 0;
      state.record = null;
      state.dirty = false;
      $("record-form").replaceChildren();
      $("edit-actions").hidden = true;
      await loadRecords();
    });
}
$("reload").onclick = () => task(loadRecords);
let searchTimer;
$("search").oninput = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(
    () =>
      task(async () => {
        state.offset = 0;
        await loadRecords();
      }),
    300,
  );
};
$("prev").onclick = () =>
  task(async () => {
    state.offset = Math.max(0, state.offset - 100);
    await loadRecords();
  });
$("next").onclick = () =>
  task(async () => {
    state.offset += 100;
    await loadRecords();
  });
$("new").onclick = () =>
  task(async () => {
    if (!warnUnsaved()) return;
    const { kind, island, resource } = params();
    const payload =
      kind === "live-point" ? {name:"Nowy punkt Live",latitude:null,longitude:null,hidden:false} : kind === "guide"
        ? {
            name: "Nowy artykuł",
            slug: "nowy-artykul",
            short_description: "",
            description: "",
            category: "",
            tags: [],
            featured: false,
            order: null,
            language: "es",
          }
        : kind === "explore"
          ? {
              name: "Nowe miejsce",
              description: "",
              category: "",
              latitude: null,
              longitude: null,
              ...(resource === "routes"
                ? { geometry: { type: "LineString", coordinates: [] } }
                : {}),
            }
          : kind === "calendar"
            ? {
                title: "Nowe wydarzenie",
                start_date: `${resource}-01`,
                end_date: `${resource}-01`,
                all_day: true,
                location: "",
                category:"",
                municipality:"",
                price:"",
                url:"",
                description: "",
              }
            : {
                title: "Nowa aktualność",
                summary: "",
                description: "",
                published_at: new Date().toISOString(),
                url: "",
              };
    state.record = {
      id: null,
      identity: {
        kind,
        island,
        resource,
        record_key: `new:${crypto.randomUUID()}`,
      },
      draft: payload,
      published: null,
      status: "new",
      version: 0,
      base_fingerprint: await digest(null),
    };
    renderRecord();
  });
$("save").onclick = () => task(() => save("record"));
$("publish").onclick = () => task(() => publish("record"));
$("preview").onclick = () => task(() => preview("record"));
$("history").onclick = () => task(() => showHistory("record"));
$("save-settings").onclick = () => task(() => save("settings"));
$("publish-settings").onclick = () => task(() => publish("settings"));
$("preview-settings").onclick = () => task(() => preview("settings"));
$("settings-history").onclick = () => task(() => showHistory("settings"));
$("close-preview").onclick = () => $("preview-dialog").close();
$("scope").onchange = () => {
  collectSettings();
  state.scope = $("scope").value;
  renderSettings();
};
document.querySelectorAll("[data-view]").forEach(
  (b) =>
    (b.onclick = () =>
      task(async () => {
        if (b.dataset.view === "settings" && !state.settings)
          await loadSettings();
        if (b.dataset.view === "content" && !state.recordsLoaded) await loadRecords();
        if (b.dataset.view === "media") await loadMedia();
        view(b.dataset.view);
      })),
);
$("upload").onchange = () =>
  task(async () => {
    let file = $("upload").files[0];
    if (!file) return;
    if(file.size>20_000_000)throw new Error("Wybierz zdjęcie mniejsze niż 20 MB.");
    let bitmap;try{bitmap=await createImageBitmap(file);}catch{throw new Error("Nie udało się odczytać zdjęcia. Wybierz poprawny plik JPEG, PNG lub WebP.");}const factor=Math.min(1,1920/Math.max(bitmap.width,bitmap.height));
    const canvas=document.createElement('canvas');canvas.width=Math.round(bitmap.width*factor);canvas.height=Math.round(bitmap.height*factor);canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
    file=new File([await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',0.86))],file.name.replace(/\.[^.]+$/,'.jpg'),{type:'image/jpeg'});
    if (file.size > 5_000_000)
      throw new Error("Zdjęcie może mieć najwyżej 5 MB.");
    const data = await new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result.split(",")[1]);
      r.onerror = reject;
      r.readAsDataURL(file);
    });
    await api("/media", {
      method: "POST",
      body: JSON.stringify({
        island:$("media-island").value,
        filename: file.name,
        alt:$("media-alt").value,credit:$("media-credit").value,
        data,
      }),
    });
    $("upload").value = "";
    await loadMedia();
    message("Zdjęcie dodano do biblioteki.");
  });
window.addEventListener("beforeunload", (e) => {
  if (state.dirty || state.settingsDirty) {
    e.preventDefault();
    e.returnValue = "";
  }
});
task(init);

$("close-history").onclick=()=>$("history-dialog").close();
$("rebase").onclick=()=>task(async()=>{
 const item=state.record;if(!item)throw new Error("Wybierz wpis.");const draft=recordPayload(),dirty=state.dirty;
 if(item.id){state.record=await api(`/documents/${item.id}/rebase`,{method:"POST",body:JSON.stringify({expected_version:item.version})});if(dirty)state.record.draft=draft;}
 else {const current=await api('/current?'+new URLSearchParams(item.identity));state.record={...item,draft,published:current.published,base_fingerprint:current.base_fingerprint};}
 renderRecord();state.dirty=dirty;preview("record");message("Wczytano aktualną wersję do porównania. Twoje poprawki pozostały w formularzu.");
});
$("improve-ai").onclick=()=>task(async()=>{
 if(!state.record || state.record.identity.kind!=="guide")throw new Error("Wybierz artykuł Guía do poprawy z AI.");
 const record={...state.record,draft:recordPayload()};
 if(window.parent===window){sessionStorage.setItem('cc-editor-ai-record',JSON.stringify(record));location.assign('/?edit=article');return;}
 parent.postMessage({type:"cc-editor-ai",record},location.origin);message("Otwieram formularz poprawy artykułu z AI…");
});
for(const id of ['calendar-town','calendar-category','calendar-state','calendar-from','calendar-to'])$(id).onchange=()=>task(loadRecords);
$("calendar-clear").onclick=()=>task(async()=>{for(const id of ['calendar-town','calendar-category','calendar-state','calendar-from','calendar-to','search'])$(id).value='';await loadRecords();});

for(const [id,delta] of [["calendar-prev",-1],["calendar-next",1],["calendar-today",0]]) $(id).onclick=()=>task(async()=>{
 const value=delta?new Date($("month").value+"-01T12:00:00Z"):new Date();
 if(delta)value.setUTCMonth(value.getUTCMonth()+delta);
 $("month").value=value.toISOString().slice(0,7);state.offset=0;await loadRecords();
});

window.addEventListener('message',event=>{if(event.origin!==location.origin||event.source!==parent||event.data?.type!=='cc-editor-use-image')return;const image=event.data.image;if(!state.record){message('Najpierw wybierz artykuł, wydarzenie lub miejsce. Potem wybierz zdjęcie w bibliotece.',true);return;}state.record.draft={...recordPayload(),image_url:image.url,image_alt:image.alt||image.filename,image_credit:image.credit||''};renderRecord();state.dirty=true;view('content');message('Zdjęcie przypisano do formularza. Zapisz szkic, aby zachować wybór.');});
