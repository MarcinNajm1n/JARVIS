const statusDot = document.querySelector("#statusDot");
const stateLabel = document.querySelector("#stateLabel");
const transcript = document.querySelector("#transcript");
const micButton = document.querySelector("#micButton");
const endRecordButton = document.querySelector("#endRecordButton");
const stopButton = document.querySelector("#stopButton");
const textForm = document.querySelector("#textForm");
const textInput = document.querySelector("#textInput");

const isFilePreview = location.protocol === "file:";
let socket = null;
let isRecording = false;

if (!isFilePreview) {
  socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/ws`);
}

function setState(state) {
  const normalized = state.toLowerCase();
  stateLabel.textContent = state;
  statusDot.className = `status-dot ${normalized}`;
  document.body.dataset.state = normalized;
  endRecordButton.disabled = normalized !== "listening";
  if (normalized !== "listening") {
    isRecording = false;
    micButton.textContent = "REC";
  }
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
    setState(message.state || "IDLE");

    if (message.state === "THINKING") {
      transcript.textContent += message.payload || "";
      return;
    }

    if (message.payload) {
      transcript.textContent = message.payload;
    }
  });
} else {
  transcript.textContent = "Uruchom aplikacje przez python jarvis_app.py albo python main.py.";
}

micButton.addEventListener("click", () => {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    transcript.textContent = "Backend nie jest uruchomiony. Start: python jarvis_app.py";
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
  if (!isRecording && document.body.dataset.state !== "listening") {
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

endRecordButton.disabled = true;

textForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const payload = textInput.value.trim();
  if (!payload) {
    return;
  }
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    transcript.textContent = "Backend nie jest uruchomiony. Start: python jarvis_app.py";
    return;
  }
  transcript.textContent = "";
  textInput.value = "";
  socket.send(JSON.stringify({ type: "text", payload }));
});
