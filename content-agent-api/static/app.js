const CONTENT_API = "/api/v1/content";
const PHOTO_API = "/api/v1/photos";

const state = {
  currentThreadId: null,
  pollTimer: null,
  currentPhotoId: null,
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
  } catch (_) {
    badge.textContent = "API · offline";
    badge.className = "status-dot status-error";
  }
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

async function loadJsonResult(threadId) {
  try {
    const response = await fetch(`${CONTENT_API}/${threadId}/file`);
    if (!response.ok) throw new Error("Nie udało się pobrać finalnego JSON-a.");
    const data = await response.json();
    $("json-output").textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    $("json-output").textContent = error.message;
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
// PHOTO MANAGER
// -------------------------------------------------------------------------------------------------

async function scanPhotos() {
  const button = $("scan-photos");
  button.disabled = true;
  button.textContent = "Scanning…";
  try {
    const result = await apiFetch(`${PHOTO_API}/scan`, { method: "POST" });
    toast(`${result.source}: found ${result.found}, new ${result.created}, known ${result.existing}`);
    await loadPhotos();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Scan folders";
  }
}

async function loadPhotos() {
  const filter = $("photo-status-filter").value;
  const url = filter ? `${PHOTO_API}?status=${encodeURIComponent(filter)}` : PHOTO_API;
  const list = $("photo-list");
  try {
    const photos = await apiFetch(url);
    $("photo-count").textContent = photos.length;
    if (!photos.length) {
      list.innerHTML = '<p class="muted">Brak zdjęć dla tego filtra.</p>';
      return;
    }
    list.innerHTML = "";
    photos.forEach((photo) => {
      const button = document.createElement("button");
      button.className = `photo-item ${photo.photo_id === state.currentPhotoId ? "active" : ""}`;
      const location = [photo.island, photo.municipality, photo.place].filter(Boolean).join(" · ") || "brak lokalizacji";
      button.innerHTML = `
        <img src="${PHOTO_API}/${photo.photo_id}/preview" alt="" loading="lazy" />
        <div class="photo-item-copy">
          <strong>${escapeHtml(photo.current_name)}</strong>
          <span>${escapeHtml(location)}</span>
          <small>${escapeHtml(photo.status)} · ${escapeHtml(photo.folder_path || "/")}</small>
        </div>`;
      button.addEventListener("click", () => selectPhoto(photo.photo_id));
      list.appendChild(button);
    });
  } catch (error) {
    list.innerHTML = '<p class="muted">Nie udało się pobrać zdjęć.</p>';
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

  $("photo-island").value = photo.island || "";
  $("photo-municipality").value = photo.municipality || "";
  $("photo-place").value = photo.place || "";
  $("photo-category").value = photo.category || "";
  $("photo-alt").value = photo.alt_es || "";
  $("photo-tags").value = (photo.tags || []).join(", ");
  $("photo-filename").value = photo.suggested_filename || photo.current_name;

  const locked = ["approved", "skipped"].includes(photo.status);
  $("photo-form").querySelectorAll("input, textarea, button").forEach((el) => { el.disabled = locked; });
}

function photoPayload() {
  return {
    island: $("photo-island").value.trim(),
    municipality: $("photo-municipality").value.trim(),
    place: $("photo-place").value.trim(),
    category: $("photo-category").value.trim(),
    alt_es: $("photo-alt").value.trim(),
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
    await loadPhotos();
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
    const current = state.currentPhotoId;
    state.currentPhotoId = null;
    await loadPhotos();
    if (action === "approve") {
      try {
        const refreshed = await apiFetch(`${PHOTO_API}/${current}`);
        state.currentPhotoId = current;
        renderPhoto(refreshed);
      } catch (_) {}
    } else {
      clearPhotoSelection();
    }
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
}

// -------------------------------------------------------------------------------------------------
// APP
// -------------------------------------------------------------------------------------------------

function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", async () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
      tab.classList.add("active");
      $(`view-${tab.dataset.view}`).classList.add("active");
      if (tab.dataset.view === "photos") await loadPhotos();
    });
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  initTabs();
  $("create-form").addEventListener("submit", createDraft);
  $("approve-button").addEventListener("click", () => sendDecision("approve"));
  $("revise-button").addEventListener("click", () => sendDecision("revise"));
  $("refresh-list").addEventListener("click", loadDrafts);

  $("scan-photos").addEventListener("click", scanPhotos);
  $("photo-status-filter").addEventListener("change", loadPhotos);
  $("photo-form").addEventListener("submit", savePhotoMetadata);
  $("photo-approve").addEventListener("click", () => decidePhoto("approve"));
  $("photo-skip").addEventListener("click", () => decidePhoto("skip"));

  await checkHealth();
  await loadDrafts();
});
