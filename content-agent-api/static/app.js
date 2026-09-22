const CONTENT_API = "/api/v1/content";
const PHOTO_API = "/api/v1/photos";

const state = {
  currentThreadId: null,
  pollTimer: null,
  currentPhotoId: null,
  currentPhotoFolder: "",
  contentLanguages: ["es", "en", "pl"],
  canariasPublishEnabled: false,
  currentPackage: null,
  previewLanguage: null,
};

const $ = (id) => document.getElementById(id);

const statusToNode = {
  researching: "research",
  planning: "curate",
  awaiting_review: "human_review",
  writing: "write",
  exporting: "publish",
};

function toast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.style.borderColor = isError ? "rgba(255,139,125,.45)" : "#3a484b";
  el.classList.remove("hidden");
  window.setTimeout(() => el.classList.add("hidden"), 3600);
}

function statusClass(status) {
  if (["awaiting_review", "new", "review"].includes(status)) return "status-review";
  if (["ready", "approved"].includes(status)) return "status-ready";
  if (status === "error") return "status-error";
  if (["researching", "planning", "writing", "exporting"].includes(status)) return "status-working";
  return "status-neutral";
}

function setStatus(el, label) {
  el.className = `status-pill ${statusClass(label)}`;
  el.textContent = label || "—";
}

function setActiveGraphNode(status) {
  document.querySelectorAll(".graph-node").forEach((node) => node.classList.remove("active"));
  const graphEnd = document.querySelector(".graph-end");
  if (graphEnd) graphEnd.classList.remove("active");
  if (status === "ready") {
    if (graphEnd) graphEnd.classList.add("active");
    return;
  }
  const nodeName = statusToNode[status];
  if (!nodeName) return;
  const node = document.querySelector(`[data-node="${nodeName}"]`);
  if (node) node.classList.add("active");
}

async function apiFetch(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body !== undefined && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail || body.error || JSON.stringify(body);
    } catch (_) {}
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

async function checkHealth() {
  const badge = $("api-status");
  try {
    const health = await apiFetch("/health");
    badge.textContent = `API · ${health.status}`;
    badge.className = "status-dot status-ready";
    state.contentLanguages = Array.isArray(health.content_languages) && health.content_languages.length
      ? health.content_languages
      : ["es", "en", "pl"];
    state.canariasPublishEnabled = Boolean(health.canarias_publish_enabled);
    const languageBadge = $("language-status");
    if (languageBadge) {
      languageBadge.textContent = `Content · ${state.contentLanguages.map((lang) => lang.toUpperCase()).join(" · ")}`;
      languageBadge.className = "status-dot status-ready";
    }
    renderCanariasLanguageOptions();
    updatePublishAvailability();
  } catch (_) {
    badge.textContent = "API · offline";
    badge.className = "status-dot status-error";
  }
}

function renderCanariasLanguageOptions() {
  const select = $("canarias-language");
  if (!select) return;
  select.innerHTML = "";
  state.contentLanguages.forEach((language) => {
    select.add(new Option(language.toUpperCase(), language));
  });
  if (state.contentLanguages.includes("es")) select.value = "es";
}

function updatePublishAvailability() {
  const button = $("publish-canarias");
  const hint = $("publish-hint");
  if (!button || !hint) return;
  button.disabled = !state.canariasPublishEnabled;
  hint.textContent = state.canariasPublishEnabled
    ? "Treść trafi jako edytowalny draft do istniejącego Canarias editor/API."
    : "Dodaj CANARIAS_API_URL do .env, żeby włączyć wysyłanie do Canarias Cerca.";
}

// -------------------------------------------------------------------------------------------------
// TEXT EDITOR
// -------------------------------------------------------------------------------------------------

async function loadDrafts() {
  const list = $("draft-list");
  try {
    const drafts = await apiFetch(CONTENT_API);
    if (!drafts.length) {
      list.innerHTML = '<p class="muted">Brak draftów.</p>';
      return;
    }
    list.innerHTML = "";
    drafts.forEach((draft) => {
      const button = document.createElement("button");
      button.className = `draft-item ${draft.thread_id === state.currentThreadId ? "active" : ""}`;
      button.innerHTML = `<div class="draft-item-title"></div><div class="draft-item-meta"><span>${escapeHtml(draft.status)}</span><span>rev ${draft.revision_count}</span></div>`;
      button.querySelector(".draft-item-title").textContent = draft.topic;
      button.addEventListener("click", () => selectDraft(draft.thread_id));
      list.appendChild(button);
    });
  } catch (error) {
    list.innerHTML = '<p class="muted">Nie udało się pobrać listy.</p>';
    toast(error.message, true);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function selectDraft(threadId) {
  state.currentThreadId = threadId;
  $("empty-review").classList.add("hidden");
  $("review-content").classList.remove("hidden");
  await refreshCurrentDraft();
  await loadDrafts();
  startPolling();
}

async function refreshCurrentDraft() {
  if (!state.currentThreadId) return;
  try {
    const draft = await apiFetch(`${CONTENT_API}/${state.currentThreadId}`);
    renderDraft(draft);
    if (["awaiting_review", "ready", "error"].includes(draft.status)) stopPolling();
  } catch (error) {
    toast(error.message, true);
    stopPolling();
  }
}

function renderDraft(draft) {
  $("thread-id").textContent = draft.thread_id;
  $("review-topic").textContent = draft.topic;
  $("revision-count").textContent = draft.revision_count;
  setStatus($("current-status"), draft.status);
  setActiveGraphNode(draft.status);

  if (draft.outline) $("outline").textContent = draft.outline;
  else if (draft.status === "error") $("outline").textContent = draft.error_message || "Agent zakończył pracę błędem.";
  else $("outline").textContent = `Agent pracuje…\n\nAktualny status: ${draft.status}`;

  $("decision-box").classList.toggle("hidden", draft.status !== "awaiting_review");
  $("result-box").classList.toggle("hidden", draft.status !== "ready");

  if (draft.status === "ready") {
    $("download-link").href = `${CONTENT_API}/${draft.thread_id}/file`;
    loadJsonResult(draft.thread_id);
  }
}

function packageLanguages(data) {
  if (data && data.public_content && typeof data.public_content === "object") {
    return data.public_content;
  }
  // Backwards compatibility with v0.3 output.
  if (data && data.languages && typeof data.languages === "object") {
    return Object.fromEntries(Object.entries(data.languages).map(([language, content]) => [
      language,
      {
        title: content?.title || "",
        summary: content?.summary || "",
        body_markdown: content?.body_markdown || content?.body || "",
      },
    ]));
  }
  return {};
}

function markdownToHtml(markdown) {
  const escaped = escapeHtml(markdown || "");
  const lines = escaped.split("\n");
  const output = [];
  let inList = false;

  const inline = (value) => value
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");

  const closeList = () => {
    if (inList) {
      output.push("</ul>");
      inList = false;
    }
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      closeList();
      return;
    }
    if (trimmed.startsWith("### ")) {
      closeList();
      output.push(`<h4>${inline(trimmed.slice(4))}</h4>`);
      return;
    }
    if (trimmed.startsWith("## ")) {
      closeList();
      output.push(`<h3>${inline(trimmed.slice(3))}</h3>`);
      return;
    }
    if (trimmed.startsWith("# ")) {
      closeList();
      output.push(`<h2>${inline(trimmed.slice(2))}</h2>`);
      return;
    }
    if (/^[-*]\s+/.test(trimmed)) {
      if (!inList) {
        output.push("<ul>");
        inList = true;
      }
      output.push(`<li>${inline(trimmed.replace(/^[-*]\s+/, ""))}</li>`);
      return;
    }
    closeList();
    output.push(`<p>${inline(trimmed)}</p>`);
  });
  closeList();
  return output.join("");
}

function renderContentMeta(data) {
  const root = $("content-meta");
  root.innerHTML = "";
  const values = [
    ["type", data.type],
    ["island", data.island],
    ["category", data.category],
    ["slug", data.slug],
  ];
  values.forEach(([label, value]) => {
    if (!value) return;
    const chip = document.createElement("span");
    chip.className = "meta-chip";
    chip.innerHTML = `<small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong>`;
    root.appendChild(chip);
  });
  (data.tags || []).forEach((tag) => {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    chip.textContent = `#${tag}`;
    root.appendChild(chip);
  });
}

function renderSources(sources) {
  const root = $("preview-sources");
  root.innerHTML = "";
  if (!Array.isArray(sources) || !sources.length) {
    root.innerHTML = '<p class="muted">Brak zapisanych źródeł.</p>';
    return;
  }
  sources.forEach((source, index) => {
    const item = document.createElement("div");
    item.className = "source-item";
    const title = document.createElement("strong");
    title.textContent = source.title || `Źródło ${index + 1}`;
    item.appendChild(title);
    if (source.url) {
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = source.url;
      item.appendChild(link);
    }
    root.appendChild(item);
  });
}

function renderEditorNotes(notes) {
  const root = $("preview-notes");
  root.innerHTML = "";
  if (!Array.isArray(notes) || !notes.length) {
    root.innerHTML = '<p class="muted">Brak dodatkowych rzeczy do sprawdzenia.</p>';
    return;
  }
  const list = document.createElement("ul");
  notes.forEach((note) => {
    const item = document.createElement("li");
    item.textContent = note;
    list.appendChild(item);
  });
  root.appendChild(list);
}

function renderLanguageTabs(languages) {
  const root = $("language-tabs");
  root.innerHTML = "";
  Object.keys(languages).forEach((language) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `language-tab ${language === state.previewLanguage ? "active" : ""}`;
    button.textContent = language.toUpperCase();
    button.addEventListener("click", () => {
      state.previewLanguage = language;
      renderContentPackage(state.currentPackage);
    });
    root.appendChild(button);
  });
}

function renderContentPackage(data) {
  state.currentPackage = data;
  const languages = packageLanguages(data);
  const available = Object.keys(languages);
  if (!state.previewLanguage || !languages[state.previewLanguage]) {
    state.previewLanguage = available.includes("es") ? "es" : available[0] || null;
  }

  renderContentMeta(data);
  renderLanguageTabs(languages);
  renderSources(data.sources || (data.source_url ? [{ title: "Źródło", url: data.source_url }] : []));
  renderEditorNotes(data.editor_notes || []);

  const content = state.previewLanguage ? languages[state.previewLanguage] : null;
  $("preview-language").textContent = state.previewLanguage ? `PUBLIC CONTENT · ${state.previewLanguage.toUpperCase()}` : "PUBLIC CONTENT";
  $("preview-title").textContent = content?.title || "Brak tytułu";
  $("preview-summary").textContent = content?.summary || "";
  $("preview-body").innerHTML = markdownToHtml(content?.body_markdown || "");
}

async function loadJsonResult(threadId) {
  try {
    const response = await fetch(`${CONTENT_API}/${threadId}/file`);
    if (!response.ok) throw new Error("Nie udało się pobrać finalnego JSON-a.");
    const data = await response.json();
    $("json-output").textContent = JSON.stringify(data, null, 2);
    renderContentPackage(data);
  } catch (error) {
    $("json-output").textContent = error.message;
    $("preview-title").textContent = "Nie udało się wczytać podglądu";
    $("preview-summary").textContent = error.message;
  }
}

function toggleRawJson() {
  const output = $("json-output");
  const button = $("toggle-json");
  const hidden = output.classList.toggle("hidden");
  button.textContent = hidden ? "Pokaż raw JSON" : "Ukryj raw JSON";
}

async function publishToCanarias() {
  if (!state.currentThreadId) return;
  if (!state.canariasPublishEnabled) {
    toast("Najpierw ustaw CANARIAS_API_URL w .env.", true);
    return;
  }
  const button = $("publish-canarias");
  button.disabled = true;
  button.textContent = "Sending…";
  try {
    const result = await apiFetch(`${CONTENT_API}/${state.currentThreadId}/publish-to-canarias`, {
      method: "POST",
      body: JSON.stringify({
        section: $("canarias-section").value,
        language: $("canarias-language").value,
        featured: false,
      }),
    });
    toast(`Sent to Canarias Cerca: ${result.section}/${result.slug}`);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = !state.canariasPublishEnabled;
    button.textContent = "Send to Canarias Cerca";
  }
}

function startPolling() {
  stopPolling();
  state.pollTimer = window.setInterval(async () => {
    await refreshCurrentDraft();
    await loadDrafts();
  }, 1800);
}

function stopPolling() {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

async function createDraft(event) {
  event.preventDefault();
  const button = $("create-button");
  button.disabled = true;
  button.textContent = "Uruchamiam…";
  const payload = {
    topic: $("topic").value.trim(),
    source_text: $("source_text").value.trim(),
    source_url: $("source_url").value.trim(),
    island_hint: $("island_hint").value,
    content_type_hint: $("content_type_hint").value,
  };

  try {
    const created = await apiFetch(CONTENT_API, { method: "POST", body: JSON.stringify(payload) });
    toast("Graf wystartował.");
    await selectDraft(created.thread_id);
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Uruchom graf";
  }
}

async function sendDecision(action) {
  if (!state.currentThreadId) return;
  const feedback = $("feedback").value.trim();
  const searchQuery = $("search_query").value.trim();
  if (action === "revise" && !feedback) {
    toast("Przy revise wpisz feedback.", true);
    return;
  }
  try {
    await apiFetch(`${CONTENT_API}/${state.currentThreadId}/decision`, {
      method: "POST",
      body: JSON.stringify({ action, feedback: action === "revise" ? feedback : "", search_query: action === "revise" ? searchQuery : "" }),
    });
    $("feedback").value = "";
    $("search_query").value = "";
    toast(action === "approve" ? "Zatwierdzone. Agent pisze finalną wersję." : "Feedback wysłany. Agent poprawia draft.");
    startPolling();
    await refreshCurrentDraft();
  } catch (error) {
    toast(error.message, true);
  }
}

// -------------------------------------------------------------------------------------------------
// PHOTO LIBRARY
// -------------------------------------------------------------------------------------------------

function photoStatusFilter() {
  return $("photo-status-filter").value;
}

function photoQuery(extra = {}) {
  const params = new URLSearchParams();
  const status = photoStatusFilter();
  if (status) params.set("status", status);
  Object.entries(extra).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, value);
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function scanPhotos() {
  const button = $("scan-photos");
  button.disabled = true;
  button.textContent = "Scanning…";
  try {
    const result = await apiFetch(`${PHOTO_API}/scan`, { method: "POST" });
    toast(`${result.source}: found ${result.found}, new ${result.created}, known ${result.existing}`);
    await loadPhotoLibrary();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Scan folders";
  }
}

async function loadPhotoLibrary() {
  await Promise.all([loadPhotoFolders(), loadPhotos()]);
}

async function loadPhotoFolders() {
  const root = $("photo-folder-tree");
  try {
    const folders = await apiFetch(`${PHOTO_API}/folders${photoQuery()}`);
    root.innerHTML = "";

    const all = folders.find((folder) => folder.path === "") || { total_count: 0 };
    root.appendChild(folderButton("", "Wszystkie zdjęcia", all.total_count, 0));

    folders.filter((folder) => folder.path).forEach((folder) => {
      const depth = folder.path.split("/").length;
      const label = folder.path.split("/").pop();
      root.appendChild(folderButton(folder.path, label, folder.total_count, depth));
    });
  } catch (error) {
    root.innerHTML = '<p class="muted">Nie udało się pobrać folderów.</p>';
    toast(error.message, true);
  }
}

function folderButton(path, label, count, depth) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `photo-folder ${path === state.currentPhotoFolder ? "active" : ""}`;
  button.style.setProperty("--folder-depth", String(depth));
  button.innerHTML = `<span class="folder-icon">${path ? "▸" : "▦"}</span><span class="folder-name">${escapeHtml(label)}</span><span class="folder-count">${count}</span>`;
  button.title = path || "Wszystkie zdjęcia";
  button.addEventListener("click", async () => {
    state.currentPhotoFolder = path;
    clearPhotoSelection();
    await Promise.all([loadPhotoFolders(), loadPhotos()]);
  });
  return button;
}

async function loadPhotos() {
  const gallery = $("photo-gallery");
  const extra = state.currentPhotoFolder ? { folder: state.currentPhotoFolder } : {};
  try {
    const photos = await apiFetch(`${PHOTO_API}${photoQuery(extra)}`);
    $("photo-count").textContent = photos.length;
    $("photo-gallery-title").textContent = state.currentPhotoFolder || "Wszystkie zdjęcia";

    if (!photos.length) {
      gallery.innerHTML = '<p class="muted photo-gallery-empty">Brak zdjęć w tym folderze dla wybranego statusu.</p>';
      return;
    }

    gallery.innerHTML = "";
    photos.forEach((photo) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `photo-card ${photo.photo_id === state.currentPhotoId ? "active" : ""}`;
      const site = [photo.site_area, photo.site_section].filter(Boolean).join(" / ");
      const location = [photo.municipality, photo.place].filter(Boolean).join(" · ");
      const subtitle = site || location || photo.island || "brak metadata";
      button.innerHTML = `
        <div class="photo-card-image"><img src="${PHOTO_API}/${photo.photo_id}/preview" alt="" loading="lazy" /></div>
        <div class="photo-card-copy">
          <strong>${escapeHtml(photo.current_name)}</strong>
          <span>${escapeHtml(subtitle)}</span>
          <small>${escapeHtml(photo.status)}</small>
        </div>`;
      button.addEventListener("click", () => selectPhoto(photo.photo_id));
      gallery.appendChild(button);
    });
  } catch (error) {
    gallery.innerHTML = '<p class="muted">Nie udało się pobrać zdjęć.</p>';
    toast(error.message, true);
  }
}

async function selectPhoto(photoId) {
  state.currentPhotoId = photoId;
  try {
    const photo = await apiFetch(`${PHOTO_API}/${photoId}`);
    renderPhoto(photo);
    await loadPhotos();
  } catch (error) {
    toast(error.message, true);
  }
}

function renderPhoto(photo) {
  $("photo-preview-empty").classList.add("hidden");
  $("photo-preview-content").classList.remove("hidden");
  $("photo-editor-empty").classList.add("hidden");
  $("photo-form").classList.remove("hidden");

  $("photo-preview-title").textContent = photo.current_name;
  setStatus($("photo-status"), photo.status);
  $("photo-image").src = `${PHOTO_API}/${photo.photo_id}/preview?ts=${Date.now()}`;
  $("photo-folder").textContent = photo.folder_path || "/";
  $("photo-current-name").textContent = photo.current_name;
  $("photo-source").textContent = photo.source;

  const driveLink = $("photo-drive-link");
  if (photo.web_view_link) {
    driveLink.href = photo.web_view_link;
    driveLink.classList.remove("hidden");
  } else {
    driveLink.removeAttribute("href");
    driveLink.classList.add("hidden");
  }

  $("photo-site-area").value = photo.site_area || "";
  $("photo-site-section").value = photo.site_section || "";
  $("photo-island").value = photo.island || "";
  $("photo-municipality").value = photo.municipality || "";
  $("photo-place").value = photo.place || "";
  $("photo-category").value = photo.category || "";
  renderPhotoAltFields(photo.alt_texts || {});
  $("photo-tags").value = (photo.tags || []).join(", ");
  $("photo-filename").value = photo.suggested_filename || photo.current_name;

  const locked = ["approved", "skipped"].includes(photo.status);
  $("photo-form").querySelectorAll("input, textarea, button").forEach((el) => { el.disabled = locked; });
}

function renderPhotoAltFields(altTexts = {}) {
  const root = $("photo-alt-fields");
  if (!root) return;
  root.innerHTML = "";
  state.contentLanguages.forEach((language) => {
    const label = document.createElement("label");
    label.className = "field";
    label.innerHTML = `<span>Alt ${escapeHtml(language.toUpperCase())}</span><textarea class="photo-alt-input" data-language="${escapeHtml(language)}" rows="3" placeholder="Opis zdjęcia w języku ${escapeHtml(language.toUpperCase())}"></textarea>`;
    label.querySelector("textarea").value = altTexts[language] || "";
    root.appendChild(label);
  });
}

function collectPhotoAltTexts() {
  const result = {};
  document.querySelectorAll(".photo-alt-input").forEach((input) => {
    const value = input.value.trim();
    if (value) result[input.dataset.language] = value;
  });
  return result;
}

function photoPayload() {
  return {
    site_area: $("photo-site-area").value.trim(),
    site_section: $("photo-site-section").value.trim(),
    island: $("photo-island").value.trim(),
    municipality: $("photo-municipality").value.trim(),
    place: $("photo-place").value.trim(),
    category: $("photo-category").value.trim(),
    alt_texts: collectPhotoAltTexts(),
    tags: $("photo-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean),
    suggested_filename: $("photo-filename").value.trim(),
  };
}

async function savePhotoMetadata(event) {
  event.preventDefault();
  if (!state.currentPhotoId) return;
  try {
    const photo = await apiFetch(`${PHOTO_API}/${state.currentPhotoId}`, {
      method: "PATCH",
      body: JSON.stringify(photoPayload()),
    });
    renderPhoto(photo);
    toast("Metadata zapisane.");
    await Promise.all([loadPhotoFolders(), loadPhotos()]);
  } catch (error) {
    toast(error.message, true);
  }
}

async function decidePhoto(action) {
  if (!state.currentPhotoId) return;
  try {
    if (action === "approve") {
      await apiFetch(`${PHOTO_API}/${state.currentPhotoId}`, {
        method: "PATCH",
        body: JSON.stringify(photoPayload()),
      });
    }
    const result = await apiFetch(`${PHOTO_API}/${state.currentPhotoId}/decision`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });
    toast(action === "approve" ? `Renamed → ${result.filename}` : "Zdjęcie pominięte.");
    clearPhotoSelection();
    await loadPhotoLibrary();
  } catch (error) {
    toast(error.message, true);
  }
}

function clearPhotoSelection() {
  state.currentPhotoId = null;
  $("photo-preview-empty").classList.remove("hidden");
  $("photo-preview-content").classList.add("hidden");
  $("photo-editor-empty").classList.remove("hidden");
  $("photo-form").classList.add("hidden");
  $("photo-preview-title").textContent = "Wybierz zdjęcie";
  setStatus($("photo-status"), "—");
  renderPhotoAltFields({});
  const driveLink = $("photo-drive-link");
  if (driveLink) driveLink.classList.add("hidden");
}

// APP
// -------------------------------------------------------------------------------------------------

function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", async () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
      tab.classList.add("active");
      $(`view-${tab.dataset.view}`).classList.add("active");
      if (tab.dataset.view === "photos") await loadPhotoLibrary();
    });
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  initTabs();
  $("create-form").addEventListener("submit", createDraft);
  $("approve-button").addEventListener("click", () => sendDecision("approve"));
  $("revise-button").addEventListener("click", () => sendDecision("revise"));
  $("refresh-list").addEventListener("click", loadDrafts);
  $("toggle-json").addEventListener("click", toggleRawJson);
  $("publish-canarias").addEventListener("click", publishToCanarias);

  $("scan-photos").addEventListener("click", scanPhotos);
  $("photo-status-filter").addEventListener("change", loadPhotoLibrary);
  $("photo-form").addEventListener("submit", savePhotoMetadata);
  $("photo-approve").addEventListener("click", () => decidePhoto("approve"));
  $("photo-skip").addEventListener("click", () => decidePhoto("skip"));

  await checkHealth();
  await loadDrafts();
});
