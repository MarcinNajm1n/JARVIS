const statusDot = document.querySelector("#statusDot");
const stateLabel = document.querySelector("#stateLabel");
const transcript = document.querySelector("#transcript");
const statusPanel = document.querySelector("#statusPanel");
const llmGate = document.querySelector("#llmGate");
const wakeTranscript = document.querySelector("#wakeTranscript");
const setupWarningBlock = document.querySelector("#setupWarningBlock");
const setupWarning = document.querySelector("#setupWarning");
const taskPanel = document.querySelector("#taskPanel");
const projectPanel = document.querySelector("#projectPanel");
const systemsPanel = document.querySelector("#systemsPanel");
const costMeter = document.querySelector("#costMeter");
const tokenMeter = document.querySelector("#tokenMeter");
const briefingPanel = document.querySelector("#briefingPanel");
const memoryPanel = document.querySelector("#memoryPanel");
const micButton = document.querySelector("#micButton");
const endRecordButton = document.querySelector("#endRecordButton");
const stopButton = document.querySelector("#stopButton");
const clearTranscriptButton = document.querySelector("#clearTranscriptButton");
const historyToggleButton = document.querySelector("#historyToggleButton");
const memoryActions = document.querySelector("#memoryActions");
const saveMemoryButton = document.querySelector("#saveMemoryButton");
const ignoreMemoryButton = document.querySelector("#ignoreMemoryButton");
const textForm = document.querySelector("#textForm");
const textInput = document.querySelector("#textInput");
const resultPanel = document.querySelector("#resultPanel");
const resultMap = document.querySelector("#resultMap");
const leafletMapElement = document.querySelector("#leafletMap");
const mapMarker = document.querySelector("#mapMarker");
const mapLabel = document.querySelector("#mapLabel");
const resultImage = document.querySelector("#resultImage");
const resultTitle = document.querySelector("#resultTitle");
const resultSummary = document.querySelector("#resultSummary");
const resultDetails = document.querySelector("#resultDetails");
const resultSources = document.querySelector("#resultSources");
const resultCost = document.querySelector("#resultCost");
const eventQueue = document.querySelector("#eventQueue");
const resultHistory = document.querySelector("#resultHistory");
const commandPalette = document.querySelector("#commandPalette");

const isFilePreview = location.protocol === "file:";
let socket = null;
let isRecording = false;
let historyEnabled = true;
let visualHistory = [];
let leafletMap = null;
let leafletMarker = null;

if (!isFilePreview) {
  socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/ws`);
}

function setState(state) {
  const normalized = state.toLowerCase();
  stateLabel.textContent = state;
  statusPanel.textContent = state;
  statusDot.className = `status-dot ${normalized}`;
  document.body.dataset.state = normalized;
  const canStopRecording = normalized === "listening" || normalized === "listening_command";
  endRecordButton.disabled = !canStopRecording;
  if (!canStopRecording) {
    isRecording = false;
    micButton.textContent = "REC";
  }
}

function renderDashboard(data) {
  if (!data || typeof data !== "object") {
    return;
  }
  statusPanel.textContent = String(data.status || "idle").toUpperCase();
  historyEnabled = Boolean(data.history_enabled);
  historyToggleButton.textContent = historyEnabled ? "HISTORY ON" : "HISTORY OFF";
  const gate = data.llm_gate === "active" ? "LLM ACTIVE" : "LLM BLOCKED";
  llmGate.textContent = gate;
  llmGate.dataset.gate = data.llm_gate || "blocked_until_wake";
  const cost = data.cost || {};
  const estimatedCost = Number(cost.estimated_cost_usd || 0).toFixed(6);
  costMeter.textContent = `$${estimatedCost}`;
  tokenMeter.textContent = `in ${cost.input_tokens || 0} / out ${cost.output_tokens || 0}`;
  systemsPanel.textContent = [
    `intent: ${data.last_intent || "none"}`,
    `route: ${data.last_route || "none"}`,
    `wake: ${data.wake_detector || "unknown"}`
  ].join("\n");
  wakeTranscript.textContent = data.last_wake_transcript || "Czekam na aktywacje.";
  const warnings = Array.isArray(data.setup_warnings) ? data.setup_warnings : [];
  setupWarningBlock.hidden = warnings.length === 0;
  setupWarning.textContent = warnings.join("\n");
  projectPanel.textContent = data.project_status || data.active_project || "Brak aktywnego projektu.";
  briefingPanel.textContent = data.briefing || "Brak briefingu.";
  memoryPanel.textContent = data.memory_review || "Pamiec jest pusta.";
  if (Array.isArray(data.visual_results) && !visualHistory.length) {
    visualHistory = data.visual_results.slice(-5);
    renderVisualHistory();
  }
  taskPanel.replaceChildren();
  const tasks = Array.isArray(data.tasks) ? data.tasks : [];
  if (!tasks.length) {
    const empty = document.createElement("li");
    empty.textContent = "Brak zadan.";
    taskPanel.appendChild(empty);
  } else {
    for (const task of tasks) {
      const item = document.createElement("li");
      item.textContent = `${task.done ? "[x]" : "[ ]"} ${task.id}. ${task.title}`;
      taskPanel.appendChild(item);
    }
  }
}

function addUiEvent(text) {
  if (!eventQueue || !text) {
    return;
  }
  const item = document.createElement("li");
  item.textContent = text;
  eventQueue.appendChild(item);
  while (eventQueue.children.length > 6) {
    eventQueue.removeChild(eventQueue.firstElementChild);
  }
}

function clearResultDetails() {
  resultDetails.replaceChildren();
}

function addResultDetail(label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value ?? "brak danych";
  resultDetails.append(term, description);
}

function renderVisualResult(payload) {
  if (!payload || typeof payload !== "object") {
    return;
  }
  resultPanel.hidden = false;
  activateVisualScene(payload.mode || "generic");
  visualHistory.push(payload);
  visualHistory = visualHistory.slice(-5);
  renderVisualHistory();
  if (payload.mode === "weather" || payload.mode === "map_weather") {
    renderWeatherResult(payload);
  } else if (payload.mode === "entity_profile") {
    renderEntityProfile(payload);
  } else {
    renderGenericResult(payload);
  }
}

function renderWeatherResult(payload) {
  const weather = payload.weather || {};
  const ok = payload.ok !== false;
  const title = payload.location || "Pogoda";
  resultTitle.textContent = ok ? title : "Brak danych";
  resultSummary.textContent = ok
    ? payload.message || `${title}: aktualna pogoda.`
    : payload.message || `Nie mam aktualnych danych pogodowych dla: ${title}.`;
  mapLabel.textContent = title.toUpperCase();
  resultMap.dataset.mode = ok ? "map_weather" : "unavailable";
  const lat = Number(payload.lat || 0);
  const lon = Number(payload.lon || 0);
  renderMapLocation(lat, lon, title, ok);
  hideResultImage();
  clearResultDetails();
  addResultDetail("Temperatura", formatWeatherValue(weather.temperature, "C"));
  addResultDetail("Opis", weather.description || "brak danych");
  addResultDetail("Wiatr", formatWeatherValue(weather.wind, "km/h"));
  addResultDetail("Wilgotnosc", formatWeatherValue(weather.humidity, "%"));
  addResultDetail("Zachmurzenie", formatWeatherValue(weather.cloud_cover, "%"));
  addResultDetail("Pomiar", weather.observed_at || "brak danych");
  renderSourcesAndCost(payload);
  renderRelatedResults(payload);
}

function renderEntityProfile(payload) {
  resultTitle.textContent = payload.title || payload.subject || "Profil";
  resultSummary.textContent = payload.summary || payload.message || "Profil gotowy.";
  mapLabel.textContent = "PROFILE";
  resultMap.dataset.mode = "entity_profile";
  resetMapToProfileMode();
  renderMapImage(payload.image_url, payload.title || payload.subject);
  renderResultImage(payload.image_url, payload.title || payload.subject);
  clearResultDetails();
  const facts = Array.isArray(payload.facts) ? payload.facts : [];
  facts.slice(0, 5).forEach((fact, index) => addResultDetail(`Fakt ${index + 1}`, fact));
  renderSourcesAndCost(payload);
  renderRelatedResults(payload);
}

function renderGenericResult(payload) {
  resultTitle.textContent = payload.title || payload.mode || "RESULT";
  resultSummary.textContent = payload.message || "Wynik gotowy.";
  mapLabel.textContent = "RESULT";
  resultMap.dataset.mode = payload.mode || "generic";
  resetMapToProfileMode();
  renderMapImage(payload.image_url, payload.title || payload.mode);
  renderResultImage(payload.image_url, payload.title || payload.mode);
  clearResultDetails();
  if (payload.ok === false && payload.error) {
    addResultDetail("Powod", payload.error);
  }
  const trace = payload.planner_trace || {};
  if (trace.selected_subject) {
    addResultDetail("Kandydat", trace.selected_subject);
  }
  renderSourcesAndCost(payload);
  renderRelatedResults(payload);
}

function renderMapLocation(lat, lon, label, ok) {
  if (!ok || !Number.isFinite(lat) || !Number.isFinite(lon)) {
    resultMap.classList.remove("leaflet-ready");
    setFallbackMarker(lat, lon);
    return;
  }

  if (!window.L || !leafletMapElement) {
    renderEmbeddedOsmMap(lat, lon, label);
    return;
  }

  leafletMapElement.replaceChildren();
  resultMap.classList.add("leaflet-ready");
  resultMap.classList.remove("image-ready", "osm-embed-ready");
  if (!leafletMap) {
    leafletMap = window.L.map(leafletMapElement, {
      zoomControl: false,
      attributionControl: true,
    });
    window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap",
    }).addTo(leafletMap);
  }

  leafletMap.setView([lat, lon], 11, { animate: true });
  if (!leafletMarker) {
    leafletMarker = window.L.marker([lat, lon]).addTo(leafletMap);
  } else {
    leafletMarker.setLatLng([lat, lon]);
  }
  leafletMarker.bindPopup(label).openPopup();
  setTimeout(() => leafletMap.invalidateSize(), 80);
}

function renderEmbeddedOsmMap(lat, lon, label) {
  resultMap.classList.add("leaflet-ready", "osm-embed-ready");
  resultMap.classList.remove("image-ready");
  const span = 0.04;
  const bbox = [
    lon - span,
    lat - span,
    lon + span,
    lat + span
  ].map((value) => value.toFixed(6)).join(",");
  const iframe = document.createElement("iframe");
  iframe.className = "osm-embed";
  iframe.title = `Mapa: ${label}`;
  iframe.loading = "lazy";
  iframe.referrerPolicy = "no-referrer-when-downgrade";
  iframe.src = `https://www.openstreetmap.org/export/embed.html?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${encodeURIComponent(`${lat},${lon}`)}`;
  leafletMapElement.replaceChildren(iframe);
  setFallbackMarker(lat, lon);
}

function setFallbackMarker(lat, lon) {
  const markerX = Number.isFinite(lon) ? Math.min(86, Math.max(14, ((lon + 180) / 360) * 100)) : 50;
  const markerY = Number.isFinite(lat) ? Math.min(82, Math.max(18, 100 - ((lat + 90) / 180) * 100)) : 50;
  mapMarker.style.left = `${markerX}%`;
  mapMarker.style.top = `${markerY}%`;
}

function resetMapToProfileMode() {
  resultMap.classList.remove("leaflet-ready");
  resultMap.classList.remove("osm-embed-ready", "image-ready");
  if (leafletMapElement) {
    leafletMapElement.replaceChildren();
  }
  setFallbackMarker(0, 0);
}

function renderMapImage(imageUrl, label) {
  if (!leafletMapElement || !imageUrl) {
    return;
  }
  resultMap.classList.add("image-ready", "leaflet-ready");
  resultMap.classList.remove("osm-embed-ready");
  const image = document.createElement("img");
  image.className = "map-hero-image";
  image.src = imageUrl;
  image.alt = label ? `Obraz: ${label}` : "Obraz wyniku";
  leafletMapElement.replaceChildren(image);
}

function renderResultImage(imageUrl, label) {
  if (!resultImage || !imageUrl) {
    hideResultImage();
    return;
  }
  resultImage.hidden = false;
  resultImage.src = imageUrl;
  resultImage.alt = label ? `Obraz: ${label}` : "Obraz wyniku";
}

function hideResultImage() {
  if (!resultImage) {
    return;
  }
  resultImage.hidden = true;
  resultImage.removeAttribute("src");
  resultImage.alt = "";
}

function renderSourcesAndCost(payload) {
  const sources = Array.isArray(payload.sources) ? payload.sources : [];
  resultSources.textContent = sources.length ? `source: ${sources.join(", ")}` : "source: local";
  const cost = payload.cost || {};
  const value = Number(cost.estimated_cost_usd || 0).toFixed(6);
  resultCost.textContent = `${cost.operation || "operation"}: $${value}`;
}

function renderRelatedResults(payload) {
  const related = Array.isArray(payload.related_results) ? payload.related_results : [];
  related.slice(0, 3).forEach((item, index) => {
    const label = `Web ${index + 1}`;
    const title = item.title || item.url || "wynik";
    const source = item.source ? ` (${item.source})` : "";
    addResultDetail(label, `${title}${source}`);
  });
}

function activateVisualScene(mode) {
  document.body.dataset.visualMode = mode;
  resultPanel.classList.remove("scene-enter");
  // Restart CSS animation for consecutive visual results.
  void resultPanel.offsetWidth;
  resultPanel.classList.add("scene-enter");
}

function renderVisualHistory() {
  if (!resultHistory) {
    return;
  }
  resultHistory.replaceChildren();
  visualHistory.forEach((item, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${index + 1}`;
    button.title = item.location || item.mode || "Wynik";
    button.addEventListener("click", () => {
      if (item.mode === "weather" || item.mode === "map_weather") {
        renderWeatherResult(item);
      } else if (item.mode === "entity_profile") {
        renderEntityProfile(item);
      } else {
        renderGenericResult(item);
      }
    });
    resultHistory.appendChild(button);
  });
}

function formatWeatherValue(value, unit) {
  if (value === null || value === undefined || value === "") {
    return "brak danych";
  }
  const number = Number(value);
  const display = Number.isFinite(number)
    ? (Number.isInteger(number) ? String(number) : number.toFixed(1))
    : String(value);
  return `${display} ${unit}`;
}

function requestBrowserClose() {
  if (socket) {
    socket.close();
  }
  setTimeout(() => {
    window.open("", "_self");
    window.close();
    transcript.textContent = "JARVIS zakonczyl prace. Mozesz zamknac to okno.";
  }, 250);
}

async function requestRecordingStop() {
  try {
    if (!isFilePreview) {
      await fetch("/api/recording/stop", { method: "POST" });
    }
  } catch (_error) {
    transcript.textContent = "Nie udalo sie wyslac stop nagrywania.";
  }
}

async function requestStop() {
  try {
    if (!isFilePreview) {
      await fetch("/api/stop", { method: "POST" });
    }
  } catch (_error) {
    // The websocket stop path below is still useful when fetch is unavailable.
  }
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "stop" }));
  }
}

if (socket) {
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);

    if (message.state === "DASHBOARD") {
      renderDashboard(message.payload);
      return;
    }

    if (message.state === "CLEAR_TRANSCRIPT") {
      transcript.textContent = "";
      return;
    }

    if (message.state === "UI_EVENT") {
      addUiEvent(message.payload);
      return;
    }

    if (message.state === "VISUAL_RESULT") {
      setState("DISPLAYING_RESULT");
      renderVisualResult(message.payload);
      return;
    }

    setState(message.state || "IDLE");

    if (message.state === "SHUTDOWN") {
      transcript.textContent = message.payload || "Wylaczam JARVISA.";
      requestBrowserClose();
      return;
    }

    if (message.state === "THINKING") {
      transcript.textContent += message.payload || "";
      return;
    }

    if (message.state === "MEMORY_CANDIDATE") {
      memoryActions.hidden = false;
      transcript.textContent = message.payload || "";
      return;
    }

    if (message.payload) {
      transcript.textContent = message.payload;
    }
  });
} else {
  transcript.textContent = "Uruchom aplikacje przez .\\Uruchom_JARVIS.bat.";
}

micButton.addEventListener("click", () => {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    transcript.textContent = "Backend nie jest uruchomiony. Start: .\\Uruchom_JARVIS.bat";
    return;
  }
  if (isRecording) {
    transcript.textContent = "Koncze nagrywanie...";
    requestRecordingStop();
    return;
  }
  isRecording = true;
  endRecordButton.disabled = false;
  transcript.textContent = "";
  socket.send(JSON.stringify({ type: "listen" }));
});

endRecordButton.addEventListener("click", () => {
  if (
    !isRecording
    && document.body.dataset.state !== "listening"
    && document.body.dataset.state !== "listening_command"
  ) {
    return;
  }
  transcript.textContent = "Koncze nagrywanie...";
  requestRecordingStop();
});

stopButton.addEventListener("click", () => {
  isRecording = false;
  micButton.textContent = "REC";
  endRecordButton.disabled = true;
  requestStop();
});

clearTranscriptButton.addEventListener("click", () => {
  transcript.textContent = "";
  wakeTranscript.textContent = "";
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "clear_transcripts" }));
  }
});

historyToggleButton.addEventListener("click", () => {
  historyEnabled = !historyEnabled;
  historyToggleButton.textContent = historyEnabled ? "HISTORY ON" : "HISTORY OFF";
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "history_toggle", enabled: historyEnabled }));
  }
});

endRecordButton.disabled = true;

saveMemoryButton.addEventListener("click", () => {
  memoryActions.hidden = true;
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "memory_decision", decision: "save" }));
  }
});

ignoreMemoryButton.addEventListener("click", () => {
  memoryActions.hidden = true;
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "memory_decision", decision: "ignore" }));
  }
});

textForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const payload = textInput.value.trim();
  if (!payload) {
    return;
  }
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    transcript.textContent = "Backend nie jest uruchomiony. Start: .\\Uruchom_JARVIS.bat";
    return;
  }
  transcript.textContent = "";
  textInput.value = "";
  socket.send(JSON.stringify({ type: "text", payload }));
});

commandPalette.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-command]");
  if (!button) {
    return;
  }
  textInput.value = button.dataset.command || "";
  textInput.focus();
});

textInput.addEventListener("input", () => {
  const value = textInput.value.toLowerCase();
  commandPalette.dataset.intent = value.includes("pogoda") || value.includes("temperatura")
    ? "weather"
    : "command";
});
