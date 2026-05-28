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
const visualStage = document.querySelector("#visualStage");
const visualCloseButton = document.querySelector("#visualCloseButton");
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
const operationTimeline = document.querySelector("#operationTimeline");
const evidenceStream = document.querySelector("#evidenceStream");
const sourceCards = document.querySelector("#sourceCards");
const answerCrawl = document.querySelector("#answerCrawl");
const resultHistory = document.querySelector("#resultHistory");
const commandPalette = document.querySelector("#commandPalette");

const isFilePreview = location.protocol === "file:";
let socket = null;
let isRecording = false;
let historyEnabled = true;
let visualHistory = [];
let leafletMap = null;
let leafletMarker = null;
let visualScene = null;
let escHoldTimer = null;
let failedVisualImages = [];

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
  document.body.dataset.hudAnimations = data.hud_animations_enabled === false ? "off" : "on";
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

class VisualSceneController {
  constructor(stage, panel) {
    this.stage = stage;
    this.panel = panel;
    this.state = "idle";
    if (this.stage && this.panel) {
      this.stage.appendChild(this.panel);
    }
  }

  showSearching(payload) {
    this.open("searching", payload);
  }

  showValidation(payload) {
    this.open("validating", payload);
  }

  showGallery(payload) {
    this.open("displaying_gallery", payload);
  }

  showMap(payload) {
    this.open("displaying_map", payload);
  }

  showSearchResults(payload) {
    this.open("displaying_search_results", payload);
  }

  open(state, payload) {
    this.state = state;
    if (!this.stage || !this.panel) {
      return;
    }
    this.stage.hidden = false;
    this.stage.dataset.sceneState = state;
    this.stage.dataset.mode = payload?.mode || "generic";
    this.stage.dataset.presentation = getPresentationMode(payload || {});
    this.stage.dataset.animationProfile = payload?.animation_profile || "result";
    document.body.dataset.visualScene = "active";
    this.panel.hidden = false;
    this.panel.classList.remove("scene-enter");
    void this.panel.offsetWidth;
    this.panel.classList.add("scene-enter");
  }

  clear() {
    this.state = "returning";
    if (this.stage) {
      this.stage.dataset.sceneState = "returning";
      window.setTimeout(() => {
        this.stage.hidden = true;
        this.stage.dataset.sceneState = "idle";
        document.body.dataset.visualScene = "idle";
      }, 220);
    }
  }

  emergencyStop() {
    this.state = "emergency_stopped";
    this.clear();
  }
}

visualScene = new VisualSceneController(visualStage, resultPanel);

function renderVisualResult(payload) {
  if (!payload || typeof payload !== "object") {
    return;
  }
  activateVisualScene(payload.mode || "generic", payload);
  visualHistory.push(payload);
  visualHistory = visualHistory.slice(-5);
  renderVisualHistory();
  dispatchVisualRenderer(payload);
}

function dispatchVisualRenderer(payload) {
  resetHudSurfaces();
  if (getPresentationMode(payload) === "structured_modal") {
    renderStructuredModal(payload);
    return;
  }
  if (payload.display_type === "jarvis_tactical_hud" || payload.mode === "jarvis_tactical_hud") {
    renderTacticalHud(payload);
  } else if (payload.mode === "weather" || payload.mode === "map_weather") {
    renderWeatherResult(payload);
  } else if (payload.mode === "research_brief") {
    renderResearchBrief(payload);
  } else if (payload.mode === "entity_profile" || payload.mode === "entity_gallery") {
    renderEntityProfile(payload);
  } else {
    renderGenericResult(payload);
  }
}

function resetHudSurfaces() {
  [operationTimeline, evidenceStream, sourceCards, answerCrawl].forEach((node) => {
    if (node) {
      node.replaceChildren();
      node.hidden = true;
    }
  });
  if (resultPanel) {
    resultPanel.classList.remove("structured-modal");
    resultPanel.querySelectorAll(".structured-data-view, .tactical-search-display, .graph-display, .payload-debugger").forEach((node) => node.remove());
  }
  if (resultMap) {
    resultMap.hidden = false;
  }
}

function renderTacticalHud(payload) {
  const normalizedResults = normalizeSearchPayload(payload);
  resultTitle.textContent = payload.query || payload.question || "JARVIS TACTICAL HUD";
  resultSummary.textContent = payload.answer || payload.message || "Analiza zakonczona.";
  resultMap.dataset.mode = "jarvis_tactical_hud";
  resultPanel.dataset.confidence = payload.confidence || "medium";
  mapLabel.textContent = String(payload.confidence || "medium").toUpperCase();
  visualScene.showSearchResults(payload);
  resetMapToProfileMode();
  renderVisualDisplay(normalizedResults, payload);

  clearResultDetails();
  addResultDetail("Confidence", payload.confidence || "medium");
  addResultDetail("Checked", payload.checked_at || "brak danych");
  if (payload.fallback_notice) {
    addResultDetail("Fallback", payload.fallback_notice);
  }
  addResultDetail("Results", normalizedResults.length);
  renderOperationTimeline(payload.operations || []);
  renderEvidenceStream(payload.sources || []);
  renderSourceCards(payload.sources || []);
  renderAnswerCrawl(payload.answer || payload.message || "");
  renderSourcesAndCost(payload);
  renderTacticalSearchDisplay(payload, normalizedResults);
}

function renderHudAssetCarousel(items) {
  if (!leafletMapElement) {
    return;
  }
  resultMap.classList.add("image-ready", "leaflet-ready", "hud-carousel-ready");
  resultMap.classList.remove("osm-embed-ready");
  const carousel = document.createElement("div");
  carousel.className = "hud-asset-carousel";
  items.slice(0, 4).forEach((item, index) => {
    const frame = document.createElement("figure");
    frame.style.setProperty("--asset-index", index);
    frame.style.setProperty("--asset-delay", `${index * 3.2}s`);
    const image = document.createElement("img");
    image.src = item.url;
    image.alt = item.caption ? `Obraz: ${item.caption}` : "Obraz zrodla";
    image.loading = "lazy";
    image.style.objectFit = "contain";
    const caption = document.createElement("figcaption");
    caption.textContent = item.caption || `Asset ${index + 1}`;
    frame.append(image, caption);
    carousel.appendChild(frame);
  });
  leafletMapElement.replaceChildren(carousel);
}

function renderOperationTimeline(operations) {
  if (!operationTimeline) {
    return;
  }
  operationTimeline.hidden = false;
  operationTimeline.replaceChildren();
  const normalized = operations.length ? operations : [
    { name: "LISTENING", status: "done" },
    { name: "CLASSIFYING", status: "done" },
    { name: "SYNTHESIZING", status: "done" }
  ];
  normalized.forEach((operation, index) => {
    const item = document.createElement("span");
    item.className = `hud-operation ${operation.status || "done"}`;
    item.style.setProperty("--step-delay", `${index * 90}ms`);
    item.textContent = operation.name || "OPERATION";
    if (operation.detail) {
      item.title = operation.detail;
    }
    operationTimeline.appendChild(item);
  });
}

function renderEvidenceStream(sources) {
  if (!evidenceStream) {
    return;
  }
  evidenceStream.hidden = false;
  evidenceStream.replaceChildren();
  const list = sources.length ? sources : [{ summary: "INSUFFICIENT EVIDENCE / LOW CONFIDENCE" }];
  list.slice(0, 6).forEach((source, index) => {
    const item = document.createElement("p");
    item.style.setProperty("--stream-delay", `${index * 140}ms`);
    item.textContent = source.summary || source.title || source.url || "zrodlo";
    evidenceStream.appendChild(item);
  });
}

function renderSourceCards(sources) {
  if (!sourceCards) {
    return;
  }
  sourceCards.hidden = false;
  sourceCards.replaceChildren();
  sources.slice(0, 4).forEach((source, index) => {
    const card = document.createElement("article");
    card.className = "hud-source-card";
    card.style.setProperty("--card-delay", `${index * 120}ms`);
    const title = document.createElement("h3");
    title.textContent = source.title || "Source";
    const meta = document.createElement("p");
    const trust = source.trust_score === undefined ? "?" : Math.round(Number(source.trust_score) * 100);
    const relevance = source.relevance_score === undefined ? "?" : Math.round(Number(source.relevance_score) * 100);
    meta.textContent = `${source.provider || "web"} | trust ${trust}% | relevance ${relevance}%`;
    const url = document.createElement("small");
    url.textContent = source.url || "";
    card.append(title, meta, url);
    sourceCards.appendChild(card);
  });
}

function renderAnswerCrawl(text) {
  if (!answerCrawl) {
    return;
  }
  answerCrawl.hidden = false;
  answerCrawl.textContent = text || "";
}

function renderWeatherResult(payload) {
  resetHudSurfaces();
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
  visualScene.showMap(payload);
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
  resetHudSurfaces();
  resultTitle.textContent = payload.title || payload.subject || "Profil";
  resultSummary.textContent = payload.summary || payload.message || "Profil gotowy.";
  mapLabel.textContent = "PROFILE";
  resultMap.dataset.mode = "entity_profile";
  visualScene.showGallery(payload);
  resetMapToProfileMode();
  const mediaItems = Array.isArray(payload.media_items) ? payload.media_items : [];
  if (mediaItems.length > 1) {
    renderMediaGallery(mediaItems);
  } else {
    renderMapImage(payload.image_url, payload.title || payload.subject, {
      fit: "contain",
      position: "center center"
    });
  }
  renderResultImage(payload.image_url, payload.title || payload.subject, {
    fit: "contain",
    position: "center center"
  });
  clearResultDetails();
  const facts = Array.isArray(payload.facts) ? payload.facts : [];
  facts.slice(0, 5).forEach((fact, index) => addResultDetail(`Fakt ${index + 1}`, fact));
  renderSourcesAndCost(payload);
  renderRelatedResults(payload);
}

function renderResearchBrief(payload) {
  resetHudSurfaces();
  const normalizedResults = normalizeSearchPayload(payload);
  resultTitle.textContent = payload.title || payload.topic || "Research";
  resultSummary.textContent = payload.summary || payload.message || "Research gotowy.";
  mapLabel.textContent = "RESEARCH";
  resultMap.dataset.mode = "research_brief";
  visualScene.showGallery(payload);
  resetMapToProfileMode();

  const images = Array.isArray(payload.images) ? payload.images : [];
  const mediaItems = Array.isArray(payload.media_items) ? payload.media_items : [];
  if (mediaItems.length) {
    renderMediaGallery(mediaItems);
    renderResultImage(mediaItems[0].image_url, mediaItems[0].caption || payload.topic, mediaItems[0]);
  } else if (images.length || normalizedResults.some((result) => result.imageUrl || result.thumbnailUrl || result.media?.length)) {
    renderVisualDisplay(normalizedResults, payload);
  } else {
    renderVisualDisplay(normalizedResults, payload);
  }

  clearResultDetails();
  const validation = payload.validation || {};
  const displayValidator = validation.display_validator || {};
  addResultDetail("Pewnosc", formatConfidence(payload.confidence ?? validation.confidence));
  addResultDetail("Walidacja", displayValidator.status || validation.status || "uncertain");

  const claims = Array.isArray(payload.claims) ? payload.claims : [];
  claims.slice(0, 4).forEach((claim, index) => {
    addResultDetail(`Zrodlo ${index + 1}`, claim.claim || claim.text || claim.source_title || "brak");
  });

  const reports = Array.isArray(payload.reports) ? payload.reports : [];
  reports.slice(0, 3).forEach((report, index) => {
    addResultDetail(`Raport ${index + 1}`, report.title || report.url || "brak");
  });

  const videos = Array.isArray(payload.videos) ? payload.videos : [];
  videos.slice(0, 3).forEach((video, index) => {
    addResultDetail(`Video ${index + 1}`, video.title || video.url || "brak");
  });

  renderSourcesAndCost(payload);
  renderRelatedResults(payload);
  renderTacticalSearchDisplay(payload, normalizedResults);
}

function renderGenericResult(payload) {
  resetHudSurfaces();
  if (payload.mode === "graph" || Array.isArray(payload.nodes) || Array.isArray(payload.edges)) {
    renderGraphDisplay(payload);
    return;
  }
  const normalizedResults = normalizeSearchPayload(payload);
  resultTitle.textContent = payload.title || payload.mode || "RESULT";
  resultSummary.textContent = payload.message || "Wynik gotowy.";
  mapLabel.textContent = "RESULT";
  resultMap.dataset.mode = payload.mode || "generic";
  visualScene.showSearchResults(payload);
  resetMapToProfileMode();
  renderVisualDisplay(normalizedResults, payload);
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
  renderTacticalSearchDisplay(payload, normalizedResults);
}

function renderStructuredModal(payload) {
  const data = payload.structured_data || {};
  const columns = Array.isArray(data.columns) && data.columns.length
    ? data.columns
    : ["Pozycja", "Kwota", "Termin"];
  const rows = Array.isArray(data.rows) ? data.rows : [];
  visualScene.open("displaying_structured_modal", payload);
  resetMapToProfileMode();
  resultPanel.classList.add("structured-modal");
  resultPanel.dataset.confidence = payload.ok === false ? "low" : payload.confidence || "medium";
  resultMap.hidden = true;
  resultTitle.textContent = data.title || payload.title || "Dane tabelaryczne";
  resultSummary.textContent = data.notes || payload.summary || payload.message || "Zestawienie gotowe.";
  mapLabel.textContent = "TABLE";
  hideResultImage();
  clearResultDetails();
  addResultDetail("Prezentacja", "structured_modal");
  addResultDetail("Tryb", payload.ok === false ? "low confidence" : "czytelna tabela");
  if (data.currency) {
    addResultDetail("Waluta", data.currency);
  }
  renderSourcesAndCost(payload);

  const wrapper = document.createElement("div");
  wrapper.className = "structured-data-view";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  columns.forEach((column) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = column;
    headRow.appendChild(cell);
  });
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");
  if (rows.length) {
    rows.forEach((row) => {
      const tableRow = document.createElement("tr");
      columns.forEach((column, index) => {
        const cell = document.createElement("td");
        cell.textContent = getStructuredCell(row, column, index);
        tableRow.appendChild(cell);
      });
      tbody.appendChild(tableRow);
    });
  } else {
    const emptyRow = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = columns.length;
    cell.textContent = data.notes || payload.message || "Brak wykrytych pozycji liczbowych.";
    emptyRow.appendChild(cell);
    tbody.appendChild(emptyRow);
  }
  table.append(thead, tbody);

  if (data.total !== null && data.total !== undefined && data.total !== "") {
    const footer = document.createElement("p");
    footer.className = "structured-total";
    footer.textContent = `Razem: ${data.total} ${data.currency || ""}`.trim();
    wrapper.append(table, footer);
  } else {
    wrapper.appendChild(table);
  }
  resultPanel.appendChild(wrapper);
}

function renderTacticalSearchDisplay(payload, results = normalizeSearchPayload(payload)) {
  if (!resultPanel) {
    return;
  }
  const display = document.createElement("section");
  display.className = "tactical-search-display";
  display.dataset.testid = "search-display";
  display.dataset.resultCount = String(results.length);

  const lines = document.createElement("svg");
  lines.className = "result-connection-lines";
  lines.setAttribute("viewBox", "0 0 100 100");
  lines.setAttribute("aria-hidden", "true");
  const visibleResults = results.slice(0, 8);
  visibleResults.forEach((_result, index) => {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    const point = floatingPoint(index, visibleResults.length);
    line.setAttribute("x1", "50");
    line.setAttribute("y1", "52");
    line.setAttribute("x2", String(point.x));
    line.setAttribute("y2", String(point.y));
    line.style.setProperty("--line-delay", `${index * 120 + 180}ms`);
    lines.appendChild(line);
  });
  display.appendChild(lines);

  const field = document.createElement("div");
  field.className = "floating-result-field";
  const onlyDiagnostic = visibleResults.length === 1 && visibleResults[0].kind === "debug" && visibleResults[0].id === "debug-empty";
  if (visibleResults.length && !onlyDiagnostic) {
    visibleResults.forEach((result, index) => {
      field.appendChild(renderFloatingResultCard(result, index, visibleResults.length));
    });
  } else {
    field.appendChild(renderSearchEmptyState(payload, visibleResults[0]?.title || "NO SEARCH RESULTS RECEIVED"));
  }
  display.appendChild(field);

  if (shouldShowPayloadDebug(payload)) {
    display.appendChild(renderPayloadDebugger(payload, results));
  }
  resultPanel.appendChild(display);
}

function renderVisualDisplay(results, payload = {}) {
  if (!leafletMapElement || !resultMap) {
    return;
  }
  failedVisualImages = [];
  const normalizedResults = Array.isArray(results) ? results : normalizeSearchPayload(payload);
  const visualItems = collectVisualItems(normalizedResults, payload);
  const sources = collectSourceItems(normalizedResults, payload);
  const primary = visualItems.find((item) => item.type === "image" && item.url);

  console.debug("[JARVIS visual] visual assets extracted count", visualItems.length);
  console.debug("[JARVIS visual] primary image url", primary?.url || "none");
  console.debug("[JARVIS visual] thumbnails count", Math.max(0, visualItems.length - (primary ? 1 : 0)));

  resultMap.classList.add("image-ready", "leaflet-ready", "visual-display-ready");
  resultMap.classList.remove("osm-embed-ready", "hud-carousel-ready", "gallery-ready");

  const display = document.createElement("section");
  display.className = "visual-display";
  display.dataset.testid = "visual-display";

  if (primary) {
    const stage = document.createElement("div");
    stage.className = "visual-display-stage";
    const hero = renderImageCard(primary, 0, true);
    stage.appendChild(hero);
    if (visualItems.length > 1) {
      stage.appendChild(renderMediaStrip(primary.result || normalizedResults[0], visualItems));
    }
    display.appendChild(stage);
    renderResultImage(primary.url, primary.alt || primary.title || primary.source, {
      fit: "contain",
      position: "center center"
    });
  } else if (sources.length) {
    display.appendChild(renderSourceConstellation(sources, normalizedResults, "no image fields in payload"));
    hideResultImage();
  } else {
    display.appendChild(renderNoVisualAssets(payload, normalizedResults));
    hideResultImage();
  }

  leafletMapElement.replaceChildren(display);
}

function collectVisualItems(results, payload = {}) {
  const items = [];
  const pushAsset = (asset, fallbackResult = null) => {
    if (!asset || typeof asset !== "object") {
      return;
    }
    const url = asset.url || asset.src || asset.image_url || asset.imageUrl || asset.thumbnail_url || asset.thumbnailUrl;
    if (!url) {
      return;
    }
    items.push({
      type: asset.type || inferMediaType(url),
      url: String(url),
      alt: asset.alt || asset.caption || asset.title || fallbackResult?.title || "visual asset",
      source: asset.source || asset.provider || fallbackResult?.source || domainFromUrl(asset.source_url || fallbackResult?.url || url),
      sourceUrl: asset.source_url || fallbackResult?.url || "",
      result: fallbackResult,
      isFallback: Boolean(asset.isFallback)
    });
  };

  const payloadAssets = [
    ...(Array.isArray(payload.visual_assets) ? payload.visual_assets : []),
    ...(Array.isArray(payload.media_items) ? payload.media_items : []),
    ...(Array.isArray(payload.images) ? payload.images : [])
  ];
  payloadAssets.forEach((asset) => pushAsset(asset));

  results.forEach((result) => {
    const visual = extractVisualAssets(result);
    visual.media.forEach((asset) => pushAsset(asset, result));
    if (visual.imageUrl) {
      pushAsset({ type: "image", url: visual.imageUrl, alt: result.title, source: result.source }, result);
    }
    if (visual.thumbnailUrl) {
      pushAsset({ type: "image", url: visual.thumbnailUrl, alt: result.title, source: result.source }, result);
    }
  });

  const seen = new Set();
  return items.filter((item) => {
    if (item.type !== "image" || !item.url || seen.has(item.url)) {
      return false;
    }
    seen.add(item.url);
    return true;
  }).slice(0, 8);
}

function collectSourceItems(results, payload = {}) {
  const payloadSources = Array.isArray(payload.sources) ? payload.sources : [];
  const sourceResults = results.filter((result) => result.url || result.source || result.faviconUrl);
  const merged = [
    ...sourceResults.map((result) => ({
      title: result.title,
      source: result.source || domainFromUrl(result.url),
      url: result.url,
      faviconUrl: result.faviconUrl
    })),
    ...payloadSources.map((source) => {
      const value = source && typeof source === "object" ? source : { title: String(source || "") };
      const url = value.url || value.source_url || "";
      return {
        title: value.title || value.provider || domainFromUrl(url) || String(source || "source"),
        source: value.provider || domainFromUrl(url),
        url,
        faviconUrl: value.favicon || value.faviconUrl || value.favicon_url || faviconUrlFor(url)
      };
    })
  ];
  const seen = new Set();
  return merged.filter((source) => {
    const key = source.url || source.source || source.title;
    if (!key || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  }).slice(0, 8);
}

function renderResultImage(result, index) {
  return renderImageCard(result, index, false);
}

function renderImageCard(result, index, hero = false) {
  const frame = document.createElement("figure");
  frame.className = hero ? "visual-hero-frame visual-hero-image" : "visual-thumbnail";
  frame.style.setProperty("--visual-delay", `${index * 110}ms`);
  const image = document.createElement("img");
  image.className = "visual-image";
  image.alt = result.alt ? `Obraz: ${result.alt}` : "Obraz wyniku";
  image.loading = hero ? "eager" : "lazy";
  image.decoding = "async";
  image.dataset.originalSrc = result.url;
  image.addEventListener("load", handleImageLoad);
  image.addEventListener("error", (event) => handleImageError(event, result));
  image.src = result.url;
  const caption = document.createElement("figcaption");
  caption.className = "visual-caption";
  const title = document.createElement("strong");
  title.textContent = compactText(result.alt || result.title || "Visual preview", 96);
  const source = document.createElement("span");
  source.className = "visual-source-tag";
  source.textContent = result.source || domainFromUrl(result.sourceUrl || result.url) || "source";
  caption.append(title, source);
  frame.append(image, caption);
  return frame;
}

function renderMediaStrip(result, mediaItems) {
  const strip = document.createElement("div");
  strip.className = "visual-thumbnail-strip";
  mediaItems.slice(0, 7).forEach((item, index) => {
    const thumb = renderImageCard(item, index + 1, false);
    thumb.classList.toggle("active", index === 0);
    thumb.type = "button";
    thumb.addEventListener("click", () => {
      const heroImage = leafletMapElement?.querySelector(".visual-hero-frame .visual-image");
      const heroCaption = leafletMapElement?.querySelector(".visual-hero-frame .visual-caption");
      if (!heroImage) {
        return;
      }
      leafletMapElement.querySelectorAll(".visual-thumbnail").forEach((node) => node.classList.remove("active"));
      thumb.classList.add("active");
      heroImage.classList.remove("loaded", "error");
      heroImage.dataset.originalSrc = item.url;
      heroImage.src = item.url;
      heroImage.alt = item.alt ? `Obraz: ${item.alt}` : "Obraz wyniku";
      if (heroCaption) {
        heroCaption.replaceChildren();
        const title = document.createElement("strong");
        title.textContent = compactText(item.alt || item.title || result?.title || "Visual preview", 96);
        const source = document.createElement("span");
        source.className = "visual-source-tag";
        source.textContent = item.source || domainFromUrl(item.sourceUrl || item.url) || "source";
        heroCaption.append(title, source);
      }
    });
    strip.appendChild(thumb);
  });
  return strip;
}

function renderImageFallback(result, reason = "image unavailable") {
  const fallback = document.createElement("div");
  fallback.className = "visual-fallback";
  const label = document.createElement("strong");
  label.textContent = initialsFor(result.source || result.alt || result.url || "VIS");
  const detail = document.createElement("span");
  detail.textContent = reason;
  fallback.append(label, detail);
  return fallback;
}

function handleImageLoad(event) {
  const image = event.currentTarget;
  image.classList.add("loaded");
  image.classList.remove("error");
  console.debug("[JARVIS visual] image load success", image.dataset.originalSrc || image.src);
}

function handleImageError(event, result) {
  const image = event.currentTarget;
  const originalSrc = image.dataset.originalSrc || result?.url || image.src;
  console.debug("[JARVIS visual] image load error", originalSrc);
  if (!image.dataset.proxyAttempted && canProxyImage(originalSrc)) {
    image.dataset.proxyAttempted = "true";
    image.src = proxiedImageUrl(originalSrc);
    console.debug("[JARVIS visual] used proxy", true);
    return;
  }
  failedVisualImages.push(originalSrc);
  image.classList.add("error");
  image.classList.remove("loaded");
  const frame = image.closest(".visual-hero-frame, .visual-thumbnail");
  if (frame && !frame.querySelector(".visual-fallback")) {
    frame.appendChild(renderImageFallback(result || { url: originalSrc }, "image unavailable"));
  }
}

function renderSourceConstellation(sources, results, reason) {
  console.debug("[JARVIS visual] fallback reason", reason);
  const constellation = document.createElement("div");
  constellation.className = "source-constellation visual-fallback";
  constellation.dataset.testid = "source-constellation";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("aria-hidden", "true");
  sources.slice(0, 8).forEach((_source, index) => {
    const point = graphPoint(index, sources.length);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.classList.add("source-edge");
    line.setAttribute("x1", "50");
    line.setAttribute("y1", "50");
    line.setAttribute("x2", String(point.x));
    line.setAttribute("y2", String(point.y));
    line.style.setProperty("--edge-delay", `${index * 75}ms`);
    svg.appendChild(line);
  });
  constellation.appendChild(svg);
  sources.slice(0, 8).forEach((source, index) => {
    const point = graphPoint(index, sources.length);
    const node = document.createElement("div");
    node.className = "source-node";
    node.style.left = `${point.x}%`;
    node.style.top = `${point.y}%`;
    node.style.setProperty("--node-delay", `${index * 90}ms`);
    const icon = document.createElement("span");
    icon.className = "source-node-icon";
    if (source.faviconUrl) {
      const img = document.createElement("img");
      img.src = source.faviconUrl;
      img.alt = "";
      img.loading = "lazy";
      icon.appendChild(img);
    } else {
      icon.textContent = initialsFor(source.source || source.title || "SRC");
    }
    const label = document.createElement("span");
    label.className = "source-node-label";
    label.textContent = compactText(source.source || source.title || source.url || `source ${index + 1}`, 34);
    node.append(icon, label);
    constellation.appendChild(node);
  });
  const notice = document.createElement("p");
  notice.className = "no-visual-assets";
  notice.textContent = `NO VISUAL ASSETS RECEIVED | results: ${results.length} | showing source constellation`;
  constellation.appendChild(notice);
  return constellation;
}

function renderNoVisualAssets(payload, results) {
  const empty = document.createElement("div");
  empty.className = "no-visual-assets visual-fallback";
  empty.dataset.testid = "no-visual-assets";
  const fields = payload && typeof payload === "object" ? Object.keys(payload).slice(0, 12).join(", ") : typeof payload;
  empty.textContent = `NO VISUAL ASSETS RECEIVED | results: ${results.length} | fields: ${fields || "none"}`;
  if (shouldShowPayloadDebug(payload)) {
    const preview = document.createElement("pre");
    preview.textContent = safeJsonPreview(payload);
    empty.appendChild(preview);
  }
  return empty;
}

function renderFloatingResultCard(result, index, total) {
  const point = floatingPoint(index, total);
  const card = document.createElement("article");
  card.className = `search-result-card ${index === 0 ? "primary" : "satellite"}`;
  card.dataset.testid = "search-result-card";
  card.dataset.kind = result.kind || "result";
  card.style.left = `${point.x}%`;
  card.style.top = `${point.y}%`;
  card.style.setProperty("--card-delay", `${index * 110}ms`);
  card.style.setProperty("--float-duration", `${4.4 + (index % 4) * 0.7}s`);

  const title = document.createElement("h3");
  title.className = "search-result-title";
  title.dataset.testid = "search-result-title";
  title.textContent = result.title || "Untitled result";

  const summary = document.createElement("p");
  summary.className = "search-result-summary";
  summary.dataset.testid = "search-result-summary";
  summary.textContent = compactText(result.summary || result.raw || "Brak opisu.", index === 0 ? 320 : 170);
  if ((result.summary || "").length > summary.textContent.length) {
    summary.title = result.summary;
  }

  const tags = document.createElement("div");
  tags.className = "search-source-tags";
  const sourceTag = document.createElement("span");
  sourceTag.className = "search-source-tag";
  sourceTag.dataset.testid = "search-source-tag";
  sourceTag.textContent = sourceLabel(result);
  tags.appendChild(sourceTag);
  if (Number.isFinite(Number(result.score))) {
    const scoreTag = document.createElement("span");
    scoreTag.className = "search-source-tag";
    scoreTag.textContent = `confidence ${Math.round(Number(result.score) * 100)}%`;
    tags.appendChild(scoreTag);
  }
  if (result.date) {
    const dateTag = document.createElement("span");
    dateTag.className = "search-source-tag";
    dateTag.textContent = result.date;
    tags.appendChild(dateTag);
  }

  if (result.url) {
    const link = document.createElement("a");
    link.className = "search-result-link";
    link.href = result.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = shortUrl(result.url);
    card.append(title, summary, tags, link);
  } else {
    card.append(title, summary, tags);
  }
  return card;
}

function renderSearchEmptyState(payload, reason) {
  const empty = document.createElement("article");
  empty.className = "search-empty-state";
  empty.dataset.testid = "search-empty-state";
  const title = document.createElement("h3");
  title.textContent = reason;
  const summary = document.createElement("p");
  summary.textContent = payload && typeof payload === "object"
    ? `Payload received but no renderable fields found. Keys: ${Object.keys(payload).slice(0, 10).join(", ") || "none"}`
    : "InvalidPayloadError: payload nie jest obiektem.";
  empty.append(title, summary);
  return empty;
}

function renderPayloadDebugger(payload, results) {
  const debug = document.createElement("aside");
  debug.className = "payload-debugger";
  const timestamp = new Date().toISOString();
  const visualItems = collectVisualItems(results, payload);
  const fields = payload && typeof payload === "object" ? Object.keys(payload).slice(0, 18).join(", ") : typeof payload;
  debug.textContent = [
    `raw payload received: ${safeJsonPreview(payload)}`,
    `normalized results count: ${results.length}`,
    `visualAssetsCount: ${visualItems.length}`,
    `primaryImageUrl: ${visualItems[0]?.url || "none"}`,
    `failedImages: ${failedVisualImages.join(", ") || "none"}`,
    `fieldsDetectedInPayload: ${fields || "none"}`,
    `current UI state: ${document.body.dataset.state || "unknown"}`,
    "last event type: VISUAL_RESULT",
    `timestamp: ${timestamp}`,
    "source of data: websocket"
  ].join("\n");
  return debug;
}

function renderGraphDisplay(payload) {
  const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
  const edges = Array.isArray(payload.edges) ? payload.edges : [];
  visualScene.open("graph_ready", { ...payload, mode: "graph" });
  resetMapToProfileMode();
  resultTitle.textContent = payload.title || "GRAPH READY";
  resultSummary.textContent = payload.summary || `${nodes.length} nodes / ${edges.length} edges`;
  mapLabel.textContent = "GRAPH";
  resultMap.dataset.mode = "graph";
  hideResultImage();
  clearResultDetails();
  addResultDetail("Nodes", nodes.length);
  addResultDetail("Edges", edges.length);
  renderSourcesAndCost(payload);

  const graph = document.createElement("section");
  graph.className = "graph-display";
  graph.dataset.testid = "graph-display";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("aria-hidden", "true");
  const nodeMap = new Map();
  nodes.slice(0, 36).forEach((node, index) => {
    nodeMap.set(String(node.id || node.label || index), graphPoint(index, nodes.length));
  });
  edges.slice(0, 64).forEach((edge, index) => {
    const source = nodeMap.get(String(edge.source));
    const target = nodeMap.get(String(edge.target));
    if (!source || !target) {
      return;
    }
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.classList.add("graph-edge-line");
    line.dataset.testid = "graph-edge";
    line.setAttribute("x1", String(source.x));
    line.setAttribute("y1", String(source.y));
    line.setAttribute("x2", String(target.x));
    line.setAttribute("y2", String(target.y));
    line.style.setProperty("--edge-delay", `${index * 35}ms`);
    svg.appendChild(line);
  });
  graph.appendChild(svg);
  nodes.slice(0, 36).forEach((node, index) => {
    const point = graphPoint(index, nodes.length);
    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = "graph-node";
    marker.dataset.testid = "graph-node";
    marker.style.left = `${point.x}%`;
    marker.style.top = `${point.y}%`;
    marker.style.setProperty("--node-delay", `${index * 55}ms`);
    marker.textContent = node.label || node.id || `node ${index + 1}`;
    marker.title = node.path || node.id || marker.textContent;
    graph.appendChild(marker);
  });
  resultPanel.appendChild(graph);
}

function getStructuredCell(row, column, index) {
  if (Array.isArray(row)) {
    return row[index] ?? "";
  }
  if (!row || typeof row !== "object") {
    return "";
  }
  const key = normalizeStructuredKey(column);
  if (key === "pozycja") {
    return row.item || row.pozycja || row.name || "";
  }
  if (key === "kwota") {
    return row.amount || row.kwota || row.value || "";
  }
  if (key === "termin") {
    return row.due || row.termin || row.deadline || "";
  }
  return row[key] ?? "";
}

function normalizeStructuredKey(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function normalizeSearchPayload(payload) {
  const normalized = normalizeSearchPayloadKnown(payload).filter(Boolean);
  if (normalized.length) {
    return normalized;
  }
  return [{
    id: "debug-empty",
    title: "NO SEARCH RESULTS RECEIVED",
    summary: diagnosticSummary(payload),
    kind: "debug",
    imageUrl: "",
    thumbnailUrl: "",
    faviconUrl: "",
    media: [],
    raw: payload
  }];
}

function normalizeSearchPayloadKnown(payload) {
  if (payload === null || payload === undefined) {
    return [];
  }
  if (Array.isArray(payload)) {
    return payload.slice(0, 12).map((item, index) => normalizeResultItem(item, index, "result"));
  }
  if (typeof payload === "string") {
    return [{
      id: "string-0",
      title: compactText(payload, 80) || "Text payload",
      summary: compactText(payload, 320),
      kind: "answer",
      imageUrl: "",
      thumbnailUrl: "",
      faviconUrl: "",
      media: [],
      raw: payload
    }];
  }
  if (typeof payload !== "object") {
    return [];
  }
  if (Array.isArray(payload.normalized_results) && payload.normalized_results.length) {
    return payload.normalized_results.slice(0, 12).map((item, index) => normalizeResultItem(item, index, item.kind || "result"));
  }
  if (Array.isArray(payload.results)) {
    return payload.results.slice(0, 12).map((item, index) => normalizeResultItem(item, index, "result"));
  }
  if (Array.isArray(payload.items)) {
    return payload.items.slice(0, 12).map((item, index) => normalizeResultItem(item, index, "result"));
  }
  if (Array.isArray(payload.nodes) || Array.isArray(payload.edges)) {
    return [
      ...(payload.nodes || []).slice(0, 8).map((item, index) => normalizeResultItem(item, index, "node")),
      ...(payload.edges || []).slice(0, 4).map((item, index) => normalizeResultItem(item, index, "edge"))
    ];
  }
  const answer = payload.answer || payload.message || payload.summary || "";
  const sources = Array.isArray(payload.sources) ? payload.sources : [];
  if (answer || sources.length) {
    const visual = extractVisualAssets(payload);
    const answerResult = answer ? [{
      id: "answer-0",
      title: compactText(payload.title || payload.question || payload.query || "Odpowiedz JARVISA", 90),
      summary: compactText(answer, 420),
      kind: "answer",
      imageUrl: visual.imageUrl,
      thumbnailUrl: visual.thumbnailUrl,
      faviconUrl: visual.faviconUrl,
      media: visual.media,
      raw: { answer }
    }] : [];
    return [
      ...answerResult,
      ...sources.slice(0, 12 - answerResult.length).map((item, index) => normalizeResultItem(item, index, "source"))
    ];
  }
  if (payload.title || payload.subject || payload.topic || payload.query || payload.error) {
    return [normalizeResultItem(payload, 0, "debug")];
  }
  return [];
}

function normalizeResultItem(item, index, kind) {
  const value = item && typeof item === "object" ? item : { title: String(item ?? "") };
  const url = String(value.url || value.source_url || value.page_url || "");
  const title = value.title || value.name || value.label || value.source_title || value.id || `${kind} ${index + 1}`;
  const summary = value.summary || value.snippet || value.description || value.text || value.claim || stringifyMetadata(value.metadata) || "";
  const score = value.score ?? value.confidence ?? value.trust_score;
  const visual = extractVisualAssets(value);
  return {
    id: String(value.id || `${kind}-${index}`),
    title: compactText(title, 110),
    summary: compactText(summary, 420),
    url,
    source: compactText(normalizeSourceValue(value.source) || value.provider || domainFromUrl(url) || "", 80),
    date: String(value.date || value.published_at || value.checked_at || ""),
    score: Number.isFinite(Number(score)) ? Number(score) : undefined,
    kind,
    imageUrl: visual.imageUrl,
    thumbnailUrl: visual.thumbnailUrl,
    faviconUrl: visual.faviconUrl,
    media: visual.media,
    raw: value
  };
}

function floatingPoint(index, total) {
  if (index === 0) {
    return { x: 34, y: 42 };
  }
  const radiusX = total > 5 ? 32 : 26;
  const radiusY = total > 5 ? 28 : 22;
  const angle = (-70 + (index - 1) * (290 / Math.max(1, total - 1))) * (Math.PI / 180);
  return {
    x: Math.round(50 + Math.cos(angle) * radiusX),
    y: Math.round(50 + Math.sin(angle) * radiusY)
  };
}

function graphPoint(index, total) {
  const angle = (index / Math.max(1, total)) * Math.PI * 2;
  const ring = index % 3;
  const radius = 18 + ring * 10;
  return {
    x: Math.round(50 + Math.cos(angle) * radius),
    y: Math.round(50 + Math.sin(angle) * radius)
  };
}

function sourceLabel(result) {
  if (result.source) {
    return `source: ${result.source}`;
  }
  if (result.url) {
    return `source: ${domainFromUrl(result.url)}`;
  }
  return result.kind || "local";
}

function normalizeSourceValue(source) {
  if (typeof source === "string") {
    return source;
  }
  if (!source || typeof source !== "object") {
    return "";
  }
  if (source.url) {
    return source.title ? `${source.title} (${domainFromUrl(source.url) || source.url})` : (domainFromUrl(source.url) || source.url);
  }
  if (source.title) {
    return source.title;
  }
  if (source.provider) {
    return source.provider;
  }
  return safeJsonPreview(source);
}

function shortUrl(url) {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname.replace(/\/$/, "");
    return `${parsed.hostname.replace(/^www\./, "")}${path ? compactText(path, 34) : ""}`;
  } catch (_error) {
    return compactText(url, 46);
  }
}

function domainFromUrl(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch (_error) {
    return "";
  }
}

function stringifyMetadata(value) {
  if (!value) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.slice(0, 6).join("; ");
  }
  if (typeof value === "object") {
    return Object.entries(value).slice(0, 6).map(([key, item]) => `${key}: ${item}`).join("; ");
  }
  return String(value);
}

function compactText(value, limit) {
  const text = stringifyMetadata(value).replace(/\s+/g, " ").trim();
  return text.length <= limit ? text : `${text.slice(0, Math.max(0, limit - 3)).trim()}...`;
}

function diagnosticSummary(payload) {
  if (payload === null || payload === undefined) {
    return "Payload received but it was null.";
  }
  if (typeof payload === "object") {
    const keys = Object.keys(payload).slice(0, 10).join(", ");
    return `Payload received but no renderable fields found. Keys: ${keys || "none"}.`;
  }
  return `InvalidPayloadError: ${typeof payload}.`;
}

function safeJsonPreview(payload) {
  try {
    return compactText(JSON.stringify(payload), 900);
  } catch (_error) {
    return "InvalidPayloadError: raw payload cannot be serialized.";
  }
}

function shouldShowPayloadDebug(payload) {
  return Boolean(payload?.debug) || localStorage.getItem("jarvisDisplayDebug") === "1";
}

function extractVisualAssets(item) {
  const value = item && typeof item === "object" ? item : {};
  const imageUrl = firstVisualUrl(value, [
    "image", "imageUrl", "image_url", "preview", "previewImage", "preview_image",
    "ogImage", "og_image", "openGraphImage", "open_graph_image"
  ]);
  const thumbnailUrl = firstVisualUrl(value, ["thumbnail", "thumbnailUrl", "thumbnail_url"]);
  const faviconUrl = firstVisualUrl(value, ["favicon", "faviconUrl", "favicon_url", "icon"]) || faviconUrlFor(value.url || value.source_url || value.page_url || "");
  const media = [];
  ["media", "images", "attachments", "visual_assets"].forEach((key) => {
    media.push(...mediaEntries(value[key]));
  });
  if (imageUrl) {
    media.unshift({ type: "image", url: imageUrl, alt: value.title || value.name || value.label || "" });
  }
  if (thumbnailUrl && thumbnailUrl !== imageUrl) {
    media.push({ type: "image", url: thumbnailUrl, alt: value.title || value.name || value.label || "" });
  }
  const seen = new Set();
  return {
    imageUrl,
    thumbnailUrl,
    faviconUrl,
    media: media.filter((asset) => {
      if (!asset.url || seen.has(asset.url)) {
        return false;
      }
      seen.add(asset.url);
      return true;
    })
  };
}

function firstVisualUrl(value, keys) {
  for (const key of keys) {
    const url = extractUrl(value[key]);
    if (url) {
      return url;
    }
  }
  return "";
}

function extractUrl(value) {
  if (!value) {
    return "";
  }
  if (typeof value === "string") {
    return value.trim();
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const url = extractUrl(item);
      if (url) {
        return url;
      }
    }
    return "";
  }
  if (typeof value === "object") {
    for (const key of ["url", "src", "href", "image_url", "imageUrl", "thumbnail_url", "thumbnailUrl"]) {
      const url = extractUrl(value[key]);
      if (url) {
        return url;
      }
    }
  }
  return "";
}

function mediaEntries(value) {
  if (!value) {
    return [];
  }
  const items = Array.isArray(value) ? value : [value];
  return items.map((item) => {
    if (typeof item === "string") {
      return { type: inferMediaType(item), url: item };
    }
    if (!item || typeof item !== "object") {
      return null;
    }
    const url = extractUrl(item);
    if (!url) {
      return null;
    }
    return {
      type: item.type || item.kind || inferMediaType(url),
      url,
      alt: item.alt || item.caption || item.title || "",
      width: item.width,
      height: item.height
    };
  }).filter(Boolean).map((asset) => ({
    ...asset,
    type: ["image", "video", "unknown"].includes(String(asset.type).toLowerCase())
      ? String(asset.type).toLowerCase()
      : inferMediaType(asset.url)
  }));
}

function inferMediaType(url) {
  const path = String(url || "").split("?")[0].toLowerCase();
  if (/\.(png|jpe?g|webp|gif|avif|svg)$/.test(path)) {
    return "image";
  }
  if (/\.(mp4|webm|mov)$/.test(path)) {
    return "video";
  }
  return "unknown";
}

function faviconUrlFor(url) {
  const domain = domainFromUrl(url);
  return domain ? `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64` : "";
}

function canProxyImage(url) {
  if (isFilePreview) {
    return false;
  }
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch (_error) {
    return false;
  }
}

function proxiedImageUrl(url) {
  return `/api/image-proxy?url=${encodeURIComponent(url)}`;
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

  resultMap.classList.add("leaflet-ready");
  resultMap.classList.remove("image-ready", "osm-embed-ready");
  if (!leafletMap) {
    leafletMapElement.replaceChildren();
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
  scheduleMapInvalidate();
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
  resultMap.classList.remove("osm-embed-ready", "image-ready", "gallery-ready", "hud-carousel-ready", "visual-display-ready");
  if (leafletMap) {
    leafletMap.remove();
    leafletMap = null;
    leafletMarker = null;
  }
  if (leafletMapElement) {
    leafletMapElement.replaceChildren();
  }
  setFallbackMarker(0, 0);
}

function renderMapImage(imageUrl, label, options = {}) {
  if (!leafletMapElement || !imageUrl) {
    return;
  }
  resultMap.classList.add("image-ready", "leaflet-ready");
  resultMap.classList.remove("osm-embed-ready");
  const image = document.createElement("img");
  image.className = "map-hero-image";
  image.src = imageUrl;
  image.alt = label ? `Obraz: ${label}` : "Obraz wyniku";
  applyImageDisplayOptions(image, options);
  leafletMapElement.replaceChildren(image);
}

function renderMediaGallery(items) {
  if (!leafletMapElement) {
    return;
  }
  resultMap.classList.add("image-ready", "leaflet-ready", "gallery-ready");
  resultMap.classList.remove("osm-embed-ready");
  const gallery = document.createElement("div");
  gallery.className = "visual-media-grid";
  items.slice(0, 4).forEach((item, index) => {
    const figure = document.createElement("figure");
    figure.style.setProperty("--delay", `${index * 120}ms`);
    const image = document.createElement("img");
    image.src = item.image_url;
    image.alt = item.caption ? `Obraz: ${item.caption}` : "Obraz wyniku";
    applyImageDisplayOptions(image, item);
    figure.dataset.croppingAllowed = String(Boolean(item.cropping_allowed));
    const caption = document.createElement("figcaption");
    caption.textContent = item.caption || `Obraz ${index + 1}`;
    figure.append(image, caption);
    gallery.appendChild(figure);
  });
  leafletMapElement.replaceChildren(gallery);
}

function renderResultImage(imageUrl, label, options = {}) {
  if (imageUrl && typeof imageUrl === "object") {
    return renderImageCard(imageUrl, Number(label) || 0, false);
  }
  if (!resultImage || !imageUrl) {
    hideResultImage();
    return;
  }
  resultImage.hidden = false;
  resultImage.src = imageUrl;
  resultImage.alt = label ? `Obraz: ${label}` : "Obraz wyniku";
  applyImageDisplayOptions(resultImage, options);
}

function applyImageDisplayOptions(image, options = {}) {
  const fit = options.fit || options.object_fit || "contain";
  const position = options.position || options.object_position || "center center";
  image.dataset.fit = fit;
  image.dataset.croppingAllowed = String(Boolean(options.cropping_allowed));
  image.style.objectFit = fit;
  image.style.objectPosition = position;
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
  resultSources.textContent = sources.length
    ? `source: ${sources.map(formatSourceForDisplay).join(", ")}`
    : "source: local";
  const cost = payload.cost || {};
  const value = Number(cost.estimated_cost_usd || 0).toFixed(6);
  resultCost.textContent = `${cost.operation || "operation"}: $${value}`;
}

function formatSourceForDisplay(source) {
  if (typeof source === "string") {
    return source;
  }
  if (!source || typeof source !== "object") {
    return "unknown";
  }
  if (source.url) {
    return source.title ? `${source.title} (${domainFromUrl(source.url) || source.url})` : (domainFromUrl(source.url) || source.url);
  }
  if (source.title) {
    return source.title;
  }
  return compactText(JSON.stringify(source), 80);
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

function formatConfidence(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "brak danych";
  }
  return `${Math.round(number * 100)}%`;
}

function activateVisualScene(mode, payload = {}) {
  document.body.dataset.visualMode = mode;
  document.body.dataset.visualPresentation = getPresentationMode(payload);
  document.body.dataset.animationProfile = payload.animation_profile || "result";
  if (visualStage) {
    visualStage.dataset.presentation = getPresentationMode(payload);
    visualStage.dataset.animationProfile = payload.animation_profile || "result";
  }
}

function getPresentationMode(payload) {
  if (payload?.presentation === "structured_modal" || payload?.mode === "structured_table") {
    return "structured_modal";
  }
  return "animated_scene";
}

function scheduleMapInvalidate() {
  if (!leafletMap) {
    return;
  }
  requestAnimationFrame(() => {
    leafletMap.invalidateSize();
    setTimeout(() => leafletMap && leafletMap.invalidateSize(), 180);
  });
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
      activateVisualScene(item.mode || "generic", item);
      dispatchVisualRenderer(item);
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

async function requestEmergencyStop() {
  visualScene.emergencyStop();
  isRecording = false;
  micButton.textContent = "REC";
  endRecordButton.disabled = true;
  transcript.textContent = "Awaryjne zatrzymanie.";
  try {
    if (!isFilePreview) {
      await fetch("/api/emergency-stop", { method: "POST" });
    }
  } catch (_error) {
    await requestStop();
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

    if (message.state === "EMERGENCY_STOP") {
      setState("SLEEPING");
      visualScene.emergencyStop();
      transcript.textContent = message.payload || "Awaryjne zatrzymanie.";
      return;
    }

    if (message.state === "UI_EVENT") {
      addUiEvent(message.payload);
      return;
    }

    if (message.state === "VISUAL_RESULT" || message.state === "GRAPH_READY" || message.state === "GRAPH_UPDATED") {
      console.debug("JARVIS visual payload received", message.state, message.payload);
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

visualCloseButton.addEventListener("click", () => {
  visualScene.clear();
});

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.altKey && event.key.toLowerCase() === "q") {
    event.preventDefault();
    requestEmergencyStop();
    return;
  }
  if (event.key === "Escape" && !escHoldTimer) {
    escHoldTimer = window.setTimeout(() => {
      visualScene.clear();
      escHoldTimer = null;
    }, 2000);
  }
});

document.addEventListener("keyup", (event) => {
  if (event.key === "Escape" && escHoldTimer) {
    clearTimeout(escHoldTimer);
    escHoldTimer = null;
  }
});

if (window.ResizeObserver && visualStage) {
  const resizeObserver = new ResizeObserver(() => scheduleMapInvalidate());
  resizeObserver.observe(visualStage);
}

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
