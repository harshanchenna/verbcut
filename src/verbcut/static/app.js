// verbcut editor: minimal vanilla JS, no build step.

const state = {
  path: null,
  words: [],
  selected: new Set(),
  lastClicked: null,
  lastDeletedIndices: null, // for undo of the last manual delete
};

const el = (id) => document.getElementById(id);
const player = () => el("player");

async function api(method, url, body) {
  const resp = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }
  return resp.json();
}

function applyProjectState(data) {
  state.words = data.words;
  player().src = data.media_url;
  el("duration-info").textContent =
    `kept ${data.kept_duration.toFixed(2)}s / original ${data.duration.toFixed(2)}s`;
  renderTranscript();
  el("editor").classList.remove("hidden");
}

function renderTranscript() {
  const container = el("transcript");
  container.innerHTML = "";
  state.words.forEach((w, i) => {
    const span = document.createElement("span");
    span.className = "word";
    if (w.deleted) span.classList.add("deleted");
    if (state.selected.has(i)) span.classList.add("selected");
    span.textContent = (w.text || "·") + " ";
    span.dataset.index = i;
    span.addEventListener("click", (ev) => onWordClick(ev, i));
    container.appendChild(span);
  });
  el("delete-selection-btn").disabled = state.selected.size === 0;
}

function onWordClick(ev, i) {
  const w = state.words[i];
  player().currentTime = w.start;

  if (ev.shiftKey && state.lastClicked !== null) {
    const [lo, hi] = [state.lastClicked, i].sort((a, b) => a - b);
    for (let j = lo; j <= hi; j++) state.selected.add(j);
  } else if (ev.ctrlKey || ev.metaKey) {
    if (state.selected.has(i)) state.selected.delete(i);
    else state.selected.add(i);
  } else {
    state.selected.clear();
    state.selected.add(i);
  }
  state.lastClicked = i;
  renderTranscript();
}

async function openMedia() {
  const path = el("path-input").value.trim();
  if (!path) return;
  state.path = path;
  el("status").textContent = "Transcribing (first time) or loading...";
  try {
    const data = await api("POST", "/api/open", { path });
    applyProjectState(data);
    el("status").textContent = "Ready.";
  } catch (e) {
    el("status").textContent = `Error: ${e.message}`;
  }
}

async function deleteSelection() {
  if (state.selected.size === 0) return;
  const indices = [...state.selected];
  state.lastDeletedIndices = indices;
  const data = await api("POST", "/api/toggle-delete", {
    path: state.path,
    indices,
    deleted: true,
  });
  state.selected.clear();
  applyProjectState(data);
  el("undo-btn").disabled = false;
}

async function undoLastDelete() {
  if (!state.lastDeletedIndices) return;
  const data = await api("POST", "/api/toggle-delete", {
    path: state.path,
    indices: state.lastDeletedIndices,
    deleted: false,
  });
  state.lastDeletedIndices = null;
  applyProjectState(data);
  el("undo-btn").disabled = true;
}

async function removeFillers() {
  const data = await api("POST", "/api/remove-fillers", { path: state.path });
  applyProjectState(data);
}

async function trimSilences() {
  const data = await api("POST", "/api/trim-silences", { path: state.path });
  applyProjectState(data);
}

async function doExport() {
  const output = el("output-input").value.trim();
  if (!output) return;
  el("export-status").textContent = "Rendering...";
  try {
    const data = await api("POST", "/api/export", { path: state.path, output });
    el("export-status").textContent =
      `Done: ${data.output} (${data.kept_duration.toFixed(2)}s of ${data.original_duration.toFixed(2)}s)`;
  } catch (e) {
    el("export-status").textContent = `Error: ${e.message}`;
  }
}

el("open-btn").addEventListener("click", openMedia);
el("delete-selection-btn").addEventListener("click", deleteSelection);
el("undo-btn").addEventListener("click", undoLastDelete);
el("remove-fillers-btn").addEventListener("click", removeFillers);
el("trim-silences-btn").addEventListener("click", trimSilences);
el("export-btn").addEventListener("click", doExport);
