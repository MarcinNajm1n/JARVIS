# JARVIS - local AI voice assistant

## Overview

JARVIS is a local-first Python assistant for voice/text interaction, short-term and long-term memory, realtime web research, retrieval-augmented context and a browser-based tactical HUD. The project is built as a portfolio-grade prototype: it shows practical AI application engineering while keeping API keys and private runtime data outside the repository.

The assistant is not a production security system and should not be treated as one. It is a local development project that runs on the user's machine and uses external AI/search providers only when configured through environment variables.

## Problem

Many AI assistant prototypes mix prompts, credentials, local memory and UI logic in one place. This project focuses on a safer local workflow: secrets are loaded from environment variables, runtime artifacts stay outside Git, retrieval evidence is separated from generated answers, and the UI is kept as a local development surface.

## Project status

Active prototype / MVP.

Current focus:

- reliable local voice and text interaction,
- safer handling of API keys and runtime logs,
- realtime search with source filtering,
- local memory and RAG experiments,
- a clean public repository suitable for review by recruiters.

## Features

- Accepts text input, voice input or wake-phrase flow.
- Uses OpenAI for LLM, STT and TTS when `OPENAI_API_KEY` is configured.
- Can use ElevenLabs for optional STT/TTS when explicitly enabled.
- Keeps local conversation state, tasks, project notes, profile and long-term memory.
- Supports local RAG over files placed in `data/documents`.
- Performs realtime research through Tavily/Brave/DuckDuckGo-style providers depending on configuration.
- Renders a local browser HUD with status, sources, costs and visual search results.
- Provides a local graphify command for lightweight Markdown/TXT/JSON graph generation.

## Tech stack

- Python 3.11+
- FastAPI + WebSockets for the local UI backend
- Vanilla HTML/CSS/JavaScript for the HUD
- OpenAI Python SDK for LLM/STT/TTS
- ChromaDB + LangChain for local RAG experiments
- httpx, trafilatura and BeautifulSoup for retrieval/fetching
- pytest for tests

## Repository layout

```text
Jarvis/
|-- main.py                  # terminal entry point
|-- jarvis_app.py            # local web UI entry point
|-- requirements.txt         # Python dependencies
|-- .env.example             # safe config template, no secrets
|-- src/
|   |-- config.py            # environment-driven settings
|   |-- conversation_engine.py
|   |-- llm.py
|   |-- stt.py
|   |-- tts.py
|   |-- web_app.py
|   |-- retrieval/
|   |-- display/
|   `-- ...
|-- ui/
|   |-- index.html
|   |-- app.js
|   `-- styles.css
|-- tests/
`-- data/
    |-- documents/.gitkeep
    `-- vector_store/.gitkeep
```

Runtime files under `data/`, `.cache/`, `graphify-out/` and `.env` are intentionally ignored.

## Local development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally and add the keys you actually need. Do not commit `.env`.

Run terminal mode:

```powershell
python main.py
```

Run local web UI:

```powershell
python jarvis_app.py
```

Run tests:

```powershell
pytest
```

## Testing

The project uses `pytest`. The full local regression suite can be run with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Security-oriented tests cover environment diagnostics, secret-safe output, image proxy behavior, graphify path handling and selected command/retrieval flows.

## Environment variables

`.env.example` contains the full template. The most important variables are:

| Variable | Required | Description |
|---|---:|---|
| `OPENAI_API_KEY` | yes for LLM/STT/TTS | OpenAI API key loaded only from local environment |
| `LLM_MODEL` | no | Chat/reasoning model name |
| `STT_MODEL` | no | Speech-to-text model |
| `TTS_MODEL` | no | Text-to-speech model |
| `VOICE_PROVIDER` | no | `openai` or `elevenlabs` |
| `ELEVENLABS_API_KEY` | only for ElevenLabs | Optional ElevenLabs key |
| `TAVILY_API_KEY` | only for Tavily search | Optional realtime search provider |
| `BRAVE_SEARCH_API_KEY` | only for Brave fallback | Optional fallback search provider |
| `INPUT_MODE` | no | `text`, `voice` or `wake` |
| `HISTORY_ENABLED` | no | Enables local conversation history |
| `RAG_ENABLED` | no | Enables local document retrieval |
| `DOCUMENTS_DIR` | no | Folder for local RAG documents |
| `VECTOR_STORE_DIR` | no | Local vector store path |

Safe template:

```env
OPENAI_API_KEY=
TAVILY_API_KEY=
BRAVE_SEARCH_API_KEY=
ELEVENLABS_API_KEY=
```

## Architecture / How it works

High-level flow:

```text
User input
  -> wake/text/voice gate
  -> command handler or realtime retrieval router
  -> local memory/RAG context
  -> LLM response
  -> TTS and/or WebSocket HUD
  -> local history/cost/memory stores
```

Realtime search flow:

```text
QueryRouter
  -> RetrievalManager
  -> provider search
  -> source policy
  -> page fetch/extraction
  -> reranking
  -> evidence payload
  -> LLM answer with sources
```

The UI runs locally and is intended for development use. It is not an authenticated public web service.

## Security notes

- Real secrets must live only in `.env`, shell environment variables or a proper secret manager.
- `.env`, `.env.*`, local caches, vector stores, graph outputs, logs, audio captures and local databases are ignored by Git.
- API key diagnostics intentionally avoid printing full keys.
- OpenAI prompt text is not logged as a payload preview.
- Tool-call logs redact keys whose names look sensitive.
- The image proxy rejects local/private IPs, non-image content, oversized files and upstream redirects.
- The web graphify endpoint is restricted to paths inside this project directory.
- Runtime memory, conversation history, transcripts and generated audio can contain private data. Keep them out of public commits.

Before making the repository public, rotate any API key that was ever committed or pasted into a shared log. If a real secret was committed to Git history, deleting it from the current file is not enough.

## Privacy model

This project can process private voice, prompt, task and memory data. By default, those artifacts are local runtime files. They should not be published:

- `.env`
- `.cache/`
- `data/*.json`
- `data/**/*.mp3`
- `data/**/*.wav`
- `data/vector_store/`
- `graphify-out/`
- local logs, traces, dumps and screenshots with private content

## Limitations

- Local UI has no authentication and should be bound to localhost only.
- Provider APIs can fail, rate limit or return weak data.
- RAG quality depends on the local documents and embedding setup.
- Voice capture may contain private data; generated audio files are local artifacts.
- This is a prototype, not a hardened multi-user service.

## Graphify

The repository includes a lightweight local graph builder:

```powershell
.\.venv\Scripts\python.exe -m src.graphify_cli .
```

Generated graph files are written under `graphify-out/` and are ignored by Git because they can contain local workspace metadata.

## What I learned

- Designing an AI assistant around explicit runtime configuration instead of hardcoded secrets.
- Building a local FastAPI/WebSocket application with a responsive browser HUD.
- Separating assistant memory, retrieval evidence, command handling and UI events.
- Treating realtime answers as a retrieval and source-quality problem, not only a prompt problem.
- Adding security controls for secret handling, local logs, SSRF-prone image proxying and public repository hygiene.

## Publishing checklist

- [ ] `.env` is not tracked.
- [ ] `.env.example` contains only empty values or placeholders.
- [ ] Real API keys have never been committed, or they have been rotated and history has been cleaned.
- [ ] Runtime `data/`, `.cache/`, `graphify-out/`, logs and generated audio are not committed.
- [ ] README and screenshots contain no private data.
- [ ] Tests pass after security changes.
