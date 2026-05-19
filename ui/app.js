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

const isFilePreview = location.protocol === "file:";
let socket = null;
let isRecording = false;
let historyEnabled = true;

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
  wakeTranscript.textContent = data.last_wake_transcript || "Czekam na aktywacje.";
  const warnings = Array.isArray(data.setup_warnings) ? data.setup_warnings : [];
  setupWarningBlock.hidden = warnings.length === 0;
  setupWarning.textContent = warnings.join("\n");
  projectPanel.textContent = data.project_status || data.active_project || "Brak aktywnego projektu.";
  memoryPanel.textContent = data.memory_review || "Pamiec jest pusta.";
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
