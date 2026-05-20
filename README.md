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

## Pierwsze Uruchomienie

1. Zainstaluj zaleznosci w aktywnym `.venv`: `pip install -r requirements.txt`.
2. Skopiuj konfiguracje: `Copy-Item .env.example .env`.
3. Wpisz prawdziwy `OPENAI_API_KEY` w `.env`.
4. Upewnij sie, ze Windows widzi domyslny mikrofon.
5. Uruchom: `.\Uruchom_JARVIS.bat`.

Jesli brakuje klucza API albo mikrofonu, komunikat pojawi sie w konsoli i w panelu `SETUP` w UI. Przy problemie z mikrofonem aplikacja startuje w trybie tekstowym, z godnoscia, na jaka pozwala sytuacja.

Najwazniejsze opcje:

- `INPUT_MODE=text` - start z klawiatura.
- `INPUT_MODE=voice` - start z mikrofonem.
- `INPUT_MODE=wake` - start w trybie frazy aktywacyjnej.
- `TTS_ENABLED=true` - odpowiedzi glosowe.
- `TTS_ASYNC_PLAYBACK=true` - terminal wraca do promptu podczas mowienia, dzieki czemu `/stop` moze przerwac TTS.
- `RAG_ENABLED=true` - lokalna baza wiedzy z `data/documents`.
- `AUTO_MEMORY_ENABLED=true` - wykrywanie faktow do pamieci z potwierdzeniem.
- `MAX_HISTORY_MESSAGES=40` - do modelu i pliku rozmowy trafia maksymalnie 40 ostatnich wiadomosci.
- `HISTORY_ENABLED=true` - zapisuje historie rozmowy; mozna wylaczyc w kokpicie UI.
- `FUNCTION_CALLING_ENABLED=true` - pozwala modelowi uzywac lokalnych narzedzi dla zadan, profilu, projektu, trybu odpowiedzi i pamieci.
- `TERMINAL_UI=true` - statusy terminalowe przez `rich`, jesli biblioteka jest dostepna.
- `WAKE_PHRASE=jarvis śpisz?` - fraza aktywujaca tryb sluchania polecenia.
- `MAX_RECORD_SECONDS=12` - maksymalna dlugosc wypowiedzi.
- `COMMAND_TIMEOUT_SECONDS=10` - ile sekund JARVIS czeka na polecenie po aktywacji.
- `AWAKE_CONFIRMATION_TIMEOUT_SECONDS=10` - dodatkowe okno sluchania po pytaniu `Moge isc spac, szefie?`.
- `POST_SPEECH_SLEEP_DELAY_SECONDS=5.0` - pauza po zakonczeniu TTS zanim UI wroci do `SLEEPING`.
- `RESPONSE_TEXT_CLEAR_DELAY_SECONDS=1.0` - ile sekund po odpowiedzi glosowej tekst JARVISA moze jeszcze widniec w kokpicie.
- `FOLLOW_UP_TIMEOUT_SECONDS=10` - ile sekund po odpowiedzi JARVIS czeka na kolejne pytanie bez ponownej aktywacji.
- `COST_LOG_PATH=data/usage_costs.json` - lokalny licznik tokenow i szacowanego kosztu rozmow LLM od momentu wlaczenia pomiaru.
- `GPT_4_1_MINI_INPUT_COST_PER_1M=0.40` i `GPT_4_1_MINI_OUTPUT_COST_PER_1M=1.60` - stawki do lokalnego licznika kosztow `gpt-4.1-mini`.
- `MICROPHONE_SENSITIVITY=normal` - czulosc mikrofonu: `high`, `normal`, `low`.
- `SPEECH_END_SILENCE_SECONDS=0.9` - po takiej ciszy program konczy nagrywanie.
- `SPEECH_RMS_THRESHOLD=500` - reczny prog glosnosci dla wykrywania mowy, uzywany gdy nie ustawisz `MICROPHONE_SENSITIVITY`.
- `TRANSCRIPT_CORRECTION_ENABLED=true` - poprawia oczywiste bledy STT przed lokalnymi komendami i wyslaniem do LLM.
- `TRANSCRIPT_CORRECTION_WITH_LLM=false` - opcjonalna dodatkowa korekta transkrypcji przez LLM; domyslnie wylaczona, zeby nie wysylac dodatkowych tokenow.
- `TRANSCRIPT_CORRECTION_MIN_CONFIDENCE=0.65` - minimalna pewnosc dla lokalnej warstwy korekty.

## Uruchomienie

Glowne uruchomienie programu:

```powershell
.\Uruchom_JARVIS.bat
```

To jest domyslne wejscie do JARVISA. Plik startowy uruchamia backend, otwiera okno aplikacji i korzysta z konfiguracji `.env`.
Przy starcie program sprawdza `.env`, klucz API i domyslny mikrofon. Jesli mikrofon jest niedostepny, JARVIS pokaze komunikat i przejdzie w awaryjny tryb tekstowy.

Tryb deweloperski bez pliku `.bat`:

```powershell
python jarvis_app.py
```

Tryb terminalowy/debug:

```powershell
python jarvis_terminal.py
```

Przy `INPUT_MODE=wake` aplikacja webowa po starcie przechodzi w tryb nasluchu frazy aktywacyjnej. Cykl pracy to: `SLEEPING -> WAKE_DETECTED -> LISTENING_COMMAND -> THINKING -> SPEAKING -> LISTENING_COMMAND`, a po ciszy `AWAKE_CONFIRM -> SLEEPING`. Kazdy rozpoznany fragment nasluchu pokazuje w UI jako transkrypcje robocza, ale nie wysyla go do LLM i nie odpowiada, dopoki nie uslyszy frazy `jarvis śpisz?`. Po aktywacji JARVIS mowi krotko `Słucham.` i czeka `COMMAND_TIMEOUT_SECONDS` sekund na polecenie. Po odpowiedzi zostaje aktywny przez `FOLLOW_UP_TIMEOUT_SECONDS` sekund, wiec mozna zadac kolejne pytanie bez ponownego hasla. Jesli nic nie uslyszy, pyta `Moge isc spac, szefie?` i slucha jeszcze przez `AWAKE_CONFIRMATION_TIMEOUT_SECONDS` sekund. Do historii rozmowy zapisuje dopiero polecenie wypowiedziane po aktywacji. Rowniez tekst wpisany w UI nie trafia do LLM w trybie wake, chyba ze zawiera fraze aktywacyjna albo jest lokalna komenda zaczynajaca sie od `/`.

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
/task remove 1
/project jarvis
/project log Dodalem tryb aktywacji glosem.
/briefing
/stop
/zapamietaj Studiuje mechatronike i buduje asystenta AI.
/pamiec
/memory review
/memory edit 1 Nowa tresc wpisu pamieci.
/memory remove 1
/feedback dobra
/feedback zla
/rag status
/rag index
/voice off
/voice on
/reset
exit
```

Mozesz tez zapytac JARVISA naturalnie o komendy, np. `jak moge cie wylaczyc?`.
Asystent korzysta z lokalnego katalogu komend i powinien odpowiedziec:
`mozesz mnie wylaczyc za pomoca zwyklego jarvis wylacz sie`.

Glosowe komendy lokalne po aktywacji:

```txt
stop
jarvis stop
przestan
koniec
skoncz
jarvis wylacz sie
```

Komendy `stop`, `jarvis stop`, `przestan`, `koniec` i `skoncz` przerywaja TTS. JARVIS rozumie tez naturalne warianty aktywacji i zamkniecia, np. `jarvis aktywacja`, `jarvis online`, `jarvis wylacz`, `jarvis dezaktywacja` albo `jarvis offline`. Zamkniecie zapisuje dane, wysyla do UI sygnal zamkniecia strony i konczy dzialanie programu.

### Function Calling 2.0

Narzędzia JARVISA maja klasy ryzyka:

```txt
safe
requires_confirmation
dangerous
```

Operacje takie jak usuwanie zadan albo edycja/usuwanie pamieci wymagaja potwierdzenia `potwierdzam`. Czyszczenie calej pamieci wymaga mocniejszego potwierdzenia `potwierdzam wyczysc pamiec`.

Wywolania narzedzi sa logowane w:

```txt
data/tool_calls.json
```

Obecne narzedzia obejmuja zadania, profil, projekt, pamiec i wyszukiwanie komend.

### Kokpit UI

Panel aplikacji pokazuje:

```txt
aktualny stan: SLEEPING, LISTENING, THINKING, SPEAKING
ostatnia transkrypcje wake oddzielona od odpowiedzi
zadania
aktywny projekt
pamiec
status bramki LLM: LLM ACTIVE albo LLM BLOCKED
```

W trybie wake LLM jest zablokowany do momentu frazy `jarvis śpisz?`.
Przycisk `CLEAR LOG` czysci robocze transkrypcje w UI. Przycisk `HISTORY ON/OFF`
wlacza albo wylacza zapis historii rozmowy do `data/conversation_history.json`.

W trybie `/input voice` nacisnij Enter i mow normalnie. Program zakonczy nagrywanie po chwili ciszy, a nie po sztywnych 5 sekundach.

W trybie `/input wake` program nasluchuje krotkich fragmentow audio i czeka na fraze:

```txt
jarvis śpisz?
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

Pamiec moze miec typy:

```txt
profile
preferences
projects
facts
decisions
```

Przeglad pamieci:

```txt
/memory review
```

Starsze wiadomosci rozmowy sa streszczane do `data/conversation_summary.json`, a plik `conversation_history.json` nadal trzyma ostatnie 40 wiadomosci.

Ocena odpowiedzi:

```txt
/feedback dobra
/feedback zla
```

## Lokalny RAG

1. Wrzuc pliki `.txt`, `.md`, `.pdf`, `.py`, `.json`, `.csv`, `.yaml` do `data/documents/`.
2. Uruchom program.
3. Wpisz `/rag index`.
4. Zadawaj pytania zwiazane z dokumentami.

Indeks ChromaDB zapisuje sie w `data/vector_store/`. Jest to plik roboczy, wiec nie musi trafiac do repozytorium.

Jesli ChromaDB nie uruchomi sie lokalnie, program przechodzi na prosty fallback tekstowy dla plikow z `data/documents/` zamiast przerywac rozmowe. To jest wolniejsze i mniej semantyczne niz wektory, ale wystarcza do podstawowego MVP.

Mozesz tez poprosic naturalnie:

```txt
Jarvis, przeczytaj dokument decyzje.md i stresc decyzje.
```

JARVIS probuje odnalezc dokument po nazwie, dolacza jego tresc jako kontekst i wymusza zrodlo w odpowiedzi w formie `Zrodlo: nazwa_pliku`.

## Prywatnosc

- Bez frazy aktywacyjnej `jarvis śpisz?` polecenia glosowe nie sa wysylane do LLM.
- Logi pokazują podglad tekstu wysylanego do OpenAI jako `OpenAI payload preview`.
- Zapis historii mozna wylaczyc przez `HISTORY_ENABLED=false` albo w kokpicie UI.
- Robocze transkrypcje wake mozna wyczyscic przyciskiem `CLEAR LOG`.
- Trwale zmiany, takie jak usuwanie zadan lub pamieci, maja potwierdzenia w function calling.

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
