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
  scope: "global",
};
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
      $("login").hidden = false;
      $("workspace").hidden = true;
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
  const choices = kind === "news" ? ["canarias", ...state.options.islands] : state.options.islands;
  $("island").replaceChildren(...choices.map((v) => new Option(islandName(v), v)));
  if (choices.includes(selectedIsland)) $("island").value = selectedIsland;
  const values =
    kind === "guide"
      ? state.options.features.guide
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
        : kind === "news"
          ? ["news"]
          : [];
  $("resource").replaceChildren(
    ...values.map((v) => new Option(v.replaceAll("-", " "), v)),
  );
  $("resource").hidden = kind === "calendar";
  $("month").hidden = kind !== "calendar";
}
async function loadRecords() {
  state.offset = state.offset || 0;
  const result = await api(
    "/records?" +
      new URLSearchParams({
        ...params(),
        q: $("search").value,
        offset: state.offset,
        limit: 100,
      }),
  );
  state.total = result.count;
  $("record-list").replaceChildren();
  for (const item of result.items) {
    const b = node(
      "button",
      item.draft.name || item.draft.title || item.identity.record_key,
      { class: "record" },
    );
    b.append(
      node(
        "small",
        `${item.status} · wersja ${item.version}${item.draft.hidden ? " · ukryte" : ""}`,
      ),
    );
    b.onclick = () => {
      if (!warnUnsaved()) return;
      state.record = item;
      renderRecord();
    };
    $("record-list").append(b);
  }
  $("page").textContent =
    `${result.count ? state.offset + 1 : 0}–${state.offset + result.items.length} / ${result.count}`;
  $("prev").disabled = state.offset === 0;
  $("next").disabled = state.offset + 100 >= state.total;
  message(`Wczytano treści: ${result.count}.`);
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
    `${item.status} · wersja ${item.version}. Zapis roboczy nie zmienia strony.`;
  const fields = node("div", undefined, { class: "fields" });
  const advanced = node("details");
  advanced.append(node("summary", "Dodatkowe pola i dane strukturalne"));
  const keys = new Set([
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
        ? "Opublikować widoczność sekcji i teksty? Zmiana obejmie stronę publiczną."
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
  if (!item?.id) throw new Error("Wpis nie ma jeszcze zapisanej historii.");
  const data = await api(`/documents/${item.id}/history`);
  const root = $(which === "record" ? "history-list" : "settings-history-list");
  root.replaceChildren(
    node("h3", "Historia — przywrócenie tworzy wersję roboczą"),
  );
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
  return (config.islands[state.scope] ??= {
    sections: {},
    features: {},
    copy: {},
  });
}
function toggleSelect(kind, key, title, value) {
  const row = node("div", undefined, { class: "toggle-row" });
  const label = node("label", title),
    select = node("select");
  select.append(
    new Option(
      state.scope === "global"
        ? "Domyślnie widoczna"
        : "Dziedzicz ustawienie globalne",
      "inherit",
    ),
    new Option("Włączona", "true"),
    new Option("Wyłączona", "false"),
  );
  select.value = value === undefined ? "inherit" : String(value);
  select.onchange = () => {state.settingsDirty=true;};
  select.dataset.setting = kind;
  select.dataset.key = key;
  label.append(select);
  row.append(label);
  return row;
}
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
  root.replaceChildren(node("h3", "Główne sekcje"));
  for (const [key, title] of Object.entries(state.options.sections))
    root.append(toggleSelect("sections", key, title, scope.sections[key]));
  for (const [area, items] of Object.entries(state.options.features)) {
    const detail = node("details"),
      body = node("div");
    detail.append(
      node("summary", `Podsekcje: ${state.options.sections[area]}`),
    );
    for (const key of items)
      body.append(
        toggleSelect(
          "features",
          `${area}.${key}`,
          key.replaceAll("-", " "),
          scope.features[`${area}.${key}`],
        ),
      );
    detail.append(body);
    root.append(detail);
  }
  const texts = node("details"),
    body = node("div");
  texts.append(node("summary", "Teksty strony i nazwy sekcji"));
  const keys = { ...state.options.copy_defaults };
  for (const [area, items] of Object.entries(state.options.features))
    for (const key of items) {
      keys[`feature.${area}.${key}.title`] ??= key;
      keys[`feature.${area}.${key}.description`] ??= "";
    }
  for (const [key, fallback] of Object.entries(keys)) {
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
    input.value = scope.copy[key] ?? "";
    input.oninput = () => { toggle.checked = true; state.settingsDirty = true; };
    toggle.onchange = () => { state.settingsDirty = true; };
    label.append(input);
    row.append(label, check);
    body.append(row);
  }
  texts.append(body);
  root.append(texts);
  $("settings-state").textContent =
    `${state.settings.status} · wersja ${state.settings.version}. Wyspa może nadpisać ustawienie globalne.`;
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
    "/media?" + new URLSearchParams({ island: $("island").value }),
  );
  $("upload").disabled = !data.upload_enabled;
  $("media-status").textContent = data.upload_enabled
    ? "Plik zostanie przesłany do biblioteki. Wybór zdjęcia nie publikuje wpisu."
    : "Wgrywanie wymaga konfiguracji R2. W edytorze możesz podać istniejący URL zdjęcia.";
  $("media-list").replaceChildren();
  for (const image of data.items) {
    const b = node("button", image.filename);
    b.prepend(node("img", undefined, { src: image.url, alt: image.filename }));
    b.onclick = () => {
      if (!state.record) {
        message("Najpierw wybierz wpis w Treści strony.", true);
        return;
      }
      state.record.draft = state.record ? recordPayload() : {};
      state.record.draft.image_url = image.url;
      renderRecord();
      state.dirty = true;
      view("content");
      message("Zdjęcie przypisano do formularza. Zapisz wersję roboczą.");
    };
    $("media-list").append(b);
  }
}
function view(name) {
  document
    .querySelectorAll("[data-view]")
    .forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  for (const id of ["content", "settings", "media"])
    $(`${id}-view`).hidden = id !== name;
}
async function init() {
  state.options = await api("/options");
  $("login").hidden = true;
  $("workspace").hidden = false;
  $("logout").hidden = false;
  $("island").replaceChildren(
    ...state.options.islands.map((v) => new Option(islandName(v), v)),
  );
  $("scope").replaceChildren(
    new Option("Cała strona", "global"),
    ...state.options.islands.map((v) => new Option(islandName(v), v)),
  );
  const requested = new URLSearchParams(location.search);
  if (["guide", "explore", "calendar", "news"].includes(requested.get("kind")))
    $("kind").value = requested.get("kind");
  $("month").value = /^\d{4}-(0[1-9]|1[0-2])$/.test(
    requested.get("resource") || "",
  )
    ? requested.get("resource")
    : new Date().toISOString().slice(0, 7);
  resources();
  if ([...$("island").options].some((v) => v.value === requested.get("island")))
    $("island").value = requested.get("island");
  if (
    [...$("resource").options].some(
      (x) => x.value === requested.get("resource"),
    )
  )
    $("resource").value = requested.get("resource");
  await loadRecords();
}
$("login-form").onsubmit = (e) => {
  e.preventDefault();
  task(async () => {
    try {
      await api("/login", {
        method: "POST",
        body: JSON.stringify({ token: $("token").value }),
      });
    } finally {
      $("token").value = "";
    }
    await init();
  });
};
$("logout").onclick = () =>
  task(async () => {
    await api("/logout", { method: "POST" });
    location.reload();
  });
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
      kind === "guide"
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
        if (b.dataset.view === "media") await loadMedia();
        view(b.dataset.view);
      })),
);
$("upload").onchange = () =>
  task(async () => {
    const file = $("upload").files[0];
    if (!file) return;
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
        island: state.options.islands.includes($("island").value) ? $("island").value : state.options.islands[0],
        filename: file.name,
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
task(init).then(() => {
  if (!state.options) $("login").hidden = false;
});

$("rebase").onclick=()=>task(async()=>{if(!state.record?.id)throw new Error("Najpierw zapisz wersję roboczą.");if(state.dirty)throw new Error("Najpierw zapisz własne poprawki.");state.record=await api(`/documents/${state.record.id}/rebase`,{method:"POST",body:JSON.stringify({expected_version:state.record.version})});renderRecord();preview("record");message("Wczytano bieżącą wersję strony do porównania. Twój draft pozostał zachowany; sprawdź różnice przed publikacją.");});

$("improve-ai").onclick=()=>task(async()=>{
 if(!state.record || state.record.identity.kind!=="guide")throw new Error("Wybierz artykuł Guide do poprawy z AI.");
 if(state.dirty || state.record.identity.record_key.startsWith("new:"))throw new Error("Najpierw zapisz wersję roboczą artykułu.");
 parent.postMessage({type:"cc-editor-ai",record:state.record},location.origin);
});
