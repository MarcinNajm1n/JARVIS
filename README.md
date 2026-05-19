# JARVIS - prywatny asystent glosowy MVP

Minimalny asystent w Pythonie inspirowany J.A.R.V.I.S.-em. Zakres projektu jest celowo waski: mozg konwersacyjny, pamiec, lokalny RAG, STT i TTS. Bez computer vision, YOLO, kamer, robotyki i sterowania urzadzeniami.

## Struktura

```txt
Jarvis/
|-- main.py
|-- requirements.txt
|-- .env.example
|-- README.md
|-- src/
|   |-- config.py
|   |-- logger.py
|   |-- stt.py
|   |-- llm.py
|   |-- rag.py
|   |-- tts.py
|   |-- assistant_state.py
|   |-- profile_store.py
|   |-- task_store.py
|   |-- project_store.py
|   |-- response_modes.py
|   |-- auto_memory.py
|   |-- briefing.py
|   |-- terminal_ui.py
|   |-- chat_loop.py
|   |-- command_handler.py
|   |-- memory_store.py
|   `-- long_term_memory.py
`-- data/
    |-- documents/
    `-- vector_store/
```

## Co robi MVP

- dziala w terminalu,
- przyjmuje tekst z klawiatury albo nagranie z mikrofonu,
- transkrybuje mowe przez OpenAI Whisper API,
- wysyla rozmowe do modelu LLM przez OpenAI Responses API,
- dodaje pamiec stala z komendy `/zapamietaj`,
- opcjonalnie pobiera kontekst z lokalnych dokumentow przez LangChain + ChromaDB,
- wypisuje odpowiedz w terminalu,
- odtwarza odpowiedz przez OpenAI TTS,
- w razie problemu z mikrofonem albo TTS pozwala dalej pracowac tekstowo.
- ma stany pracy: sleeping, listening, thinking, speaking,
- obsluguje profil uzytkownika, zadania, aktywny projekt i briefing,
- potrafi proponowac automatyczny zapis waznych faktow do pamieci stalej,
- ma tryby odpowiedzi: jarvis, mentor, szybki, techniczny,
- pozwala przerwac odtwarzanie TTS komenda `/stop`.

## Instalacja

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Konfiguracja

Skopiuj plik przykladowy:

```powershell
Copy-Item .env.example .env
```

W pliku `.env` ustaw:

```env
OPENAI_API_KEY=twoj_klucz_api
```

Najwazniejsze opcje:

- `INPUT_MODE=text` - start z klawiatura.
- `INPUT_MODE=voice` - start z mikrofonem.
- `INPUT_MODE=wake` - start w trybie frazy aktywacyjnej.
- `TTS_ENABLED=true` - odpowiedzi glosowe.
- `TTS_ASYNC_PLAYBACK=true` - terminal wraca do promptu podczas mowienia, dzieki czemu `/stop` moze przerwac TTS.
- `RAG_ENABLED=true` - lokalna baza wiedzy z `data/documents`.
- `AUTO_MEMORY_ENABLED=true` - wykrywanie faktow do pamieci z potwierdzeniem.
- `MAX_HISTORY_MESSAGES=40` - do modelu i pliku rozmowy trafia maksymalnie 40 ostatnich wiadomosci.
- `TERMINAL_UI=true` - statusy terminalowe przez `rich`, jesli biblioteka jest dostepna.
- `WAKE_PHRASE=jarvis aktywacja` - fraza aktywujaca tryb sluchania polecenia.
- `MAX_RECORD_SECONDS=12` - maksymalna dlugosc wypowiedzi.
- `SPEECH_END_SILENCE_SECONDS=0.9` - po takiej ciszy program konczy nagrywanie.
- `SPEECH_RMS_THRESHOLD=500` - prog glosnosci dla wykrywania mowy.

## Uruchomienie

```powershell
python main.py
```

Przydatne komendy w aplikacji:

```txt
/pomoc
/input voice
/input wake
/input text
/mode jarvis
/mode mentor
/profile
/profile set response_style krotko i technicznie
/task add naprawic konfiguracje Chroma
/task list
/task done 1
/project jarvis
/project log Dodalem tryb aktywacji glosem.
/briefing
/stop
/zapamietaj Studiuje mechatronike i buduje asystenta AI.
/pamiec
/rag status
/rag index
/voice off
/voice on
/reset
exit
```

W trybie `/input voice` nacisnij Enter i mow normalnie. Program zakonczy nagrywanie po chwili ciszy, a nie po sztywnych 5 sekundach.

W trybie `/input wake` program nasluchuje krotkich fragmentow audio i czeka na fraze:

```txt
jarvis aktywacja
```

Po wykryciu frazy nagrywa nastepna wypowiedz jako polecenie. Ten tryb wysyla krotkie nagrania do STT, wiec zuzywa API czesciej niz zwykle `/input voice`.

## Funkcje typu JARVIS

### Stany asystenta

W terminalu pojawiaja sie statusy:

```txt
[JARVIS: SLEEPING]
[JARVIS: LISTENING]
[JARVIS: THINKING]
[JARVIS: SPEAKING]
```

To nie jest tylko kosmetyka. Kod uzywa tych stanow do uporzadkowania petli rozmowy i trybu aktywacji.

### Tryby odpowiedzi

```txt
/mode jarvis
/mode mentor
/mode szybki
/mode techniczny
```

Tryb jest zapisywany w `data/assistant_state.json` i trafia do instrukcji LLM.

### Profil uzytkownika

```txt
/profile
/profile set name Kornel
/profile set response_style krotko, praktycznie, technicznie
```

Profil jest zapisywany w `data/user_profile.json` i dodawany do kontekstu modelu.

### Zadania

```txt
/task add opis zadania
/task list
/task done 1
/task remove 1
```

Zadania sa lokalne i zapisywane w `data/tasks.json`.

### Tryb projektowy

```txt
/project jarvis
/project status
/project log decyzja techniczna albo notatka
/project list
/project stop
```

Aktywny projekt trafia do promptu modelu, wiec asystent wie, nad czym pracujesz.

### Briefing

```txt
/briefing
```

Pokazuje profil, aktywny projekt, liczbe wpisow pamieci i najblizsze zadania.

### Automatyczna pamiec

Gdy napiszesz cos w stylu:

```txt
Studiuje mechatronike.
Wole krotkie odpowiedzi.
Pracuje nad projektem Jarvis.
```

asystent zapyta, czy zapisac ten fakt w pamieci stalej.

## Lokalny RAG

1. Wrzuc pliki `.txt`, `.md`, `.pdf`, `.py`, `.json`, `.csv`, `.yaml` do `data/documents/`.
2. Uruchom program.
3. Wpisz `/rag index`.
4. Zadawaj pytania zwiazane z dokumentami.

Indeks ChromaDB zapisuje sie w `data/vector_store/`. Jest to plik roboczy, wiec nie musi trafiac do repozytorium.

Jesli ChromaDB nie uruchomi sie lokalnie, program przechodzi na prosty fallback tekstowy dla plikow z `data/documents/` zamiast przerywac rozmowe. To jest wolniejsze i mniej semantyczne niz wektory, ale wystarcza do podstawowego MVP.

## Testy

```powershell
pytest
```

## Dlaczego te biblioteki

- `openai` - jeden klient dla LLM, STT i TTS.
- `sounddevice` - proste nagrywanie mikrofonu do WAV bez budowania GUI.
- `pygame-ce` - lekki odtwarzacz plikow audio.
- `rich` - czytelne statusy terminalowe bez budowania GUI.
- `LangChain` - szybkie skladanie loaderow dokumentow, splitterow i retrievera.
- `ChromaDB` - lokalny vector store bez serwera i bez zewnetrznej bazy danych.
