# Aktualny Internet Search Plan dla JARVISA

## Cel

JARVIS ma przestac odpowiadac na pytania aktualne z samej wiedzy modelu. Jesli pytanie dotyczy danych, ktore mogly sie zmienic po treningu modelu, JARVIS ma:

1. wykryc, ze potrzebne sa aktualne dane,
2. przeszukac internet,
3. pobrac kilka mozliwie najnowszych zrodel,
4. sprawdzic zgodnosc zrodel,
5. policzyc pewnosc odpowiedzi,
6. dopiero wtedy odpowiedziec,
7. zbudowac display z pewnymi zrodlami i zdjeciami,
8. powiedziec wprost, jesli dane sa zbyt slabe.

JARVIS nie powinien mowic: "moja wiedza siega 2024". W takim przypadku powinien albo uruchomic search, albo powiedziec: "Nie mam wystarczajaco pewnych aktualnych danych".

## Obecny kontekst projektu

Wedlug grafu projektu kluczowy lancuch to:

```txt
web_app._prepare_llm_text
-> search_service.search_current_information
-> search_service.build_search_context
-> conversation_engine / LLM
-> visual_planner.plan_visual_result
-> research_orchestrator.build_research_brief
-> ui/app.js renderVisualResult
```

Najwazniejsze pliki:

```txt
src/search_service.py
src/web_search.py
src/web_app.py
src/visual_planner.py
src/research_orchestrator.py
src/research_query_planner.py
src/media_filters.py
src/llm_validator.py
ui/app.js
ui/styles.css
```

## Zasady systemowe

1. Bez aktywacji nie ma LLM ani web search.
2. Pytania aktualne zawsze ida przez search-before-answer.
3. Model nie moze zgadywac aktualnych faktow.
4. Odpowiedz musi wynikac ze zrodel przekazanych do LLM.
5. Jesli zrodla sa sprzeczne, JARVIS ma obnizyc confidence i powiedziec to wprost.
6. Jesli brak pewnych zrodel, JARVIS nie udaje pewnosci.
7. Zdjecia musza przejsc osobna walidacje zgodnosci z tematem.
8. UI pokazuje tylko zwalidowany `research_brief`.
9. Kazdy research zapisuje trace do pliku diagnostycznego.

## Etap 1: Lepsze wykrywanie pytan aktualnych

Plik:

```txt
src/search_service.py
```

Rozszerzyc `requires_current_information()` tak, aby wykrywal intencje:

```txt
aktualnie
obecnie
teraz
dzisiaj
najnowsze
ostatnie informacje
kto jest teraz
jaki jest obecny
kto jest najbogatszy
ranking
kurs
cena
wynik
premiera
prezydent
premier
CEO
pogoda
wydarzenia
wiadomosci
```

Dodac kategorie pytan:

```txt
current_person
current_company
current_ranking
current_price
current_news
current_weather
current_sports
current_politics
current_technology
```

Testy:

```txt
tests/test_search_service.py
```

Przyklady:

```txt
"kto jest teraz najbogatszy na swiecie" -> True
"kto jest obecnym CEO OpenAI" -> True
"jaka jest dzisiaj cena bitcoina" -> True
"kim byl Robert Oppenheimer" -> False
```

## Etap 2: Search-before-answer

Plik:

```txt
src/web_app.py
```

Obecny przeplyw trzeba uszczelnic:

```txt
tekst uzytkownika
-> requires_current_information()
-> jesli True: search_current_information()
-> walidacja zrodel
-> zbudowanie verified_search_context
-> dopiero potem stream_response()
```

Jesli `requires_current_information()` zwraca True, to LLM nie moze dostac samego pytania. Musi dostac:

```txt
pytanie uzytkownika
verified_search_context
instrukcja: odpowiadaj tylko na podstawie zrodel
instrukcja: jesli zrodla sa slabe, powiedz to wprost
```

Przyklad promptu kontekstowego:

```txt
To pytanie wymaga aktualnych danych.
Nie korzystaj z wiedzy modelu jako zrodla prawdy.
Odpowiedz tylko na podstawie ponizszych zrodel.
Jesli zrodla nie potwierdzaja odpowiedzi, powiedz: "Nie mam wystarczajaco pewnych aktualnych danych".
```

## Etap 3: Provider wyszukiwania

Obecny fallback DuckDuckGo/Wikipedia zostaje jako tryb darmowy, ale docelowo trzeba dodac provider z realnym web/news/image search.

Docelowy folder:

```txt
src/search_providers/
```

Pliki:

```txt
base.py
duckduckgo_provider.py
brave_provider.py
serpapi_provider.py
wikipedia_provider.py
news_provider.py
image_provider.py
video_provider.py
report_provider.py
```

Interfejs:

```python
class SearchProvider:
    def search_web(self, query, filters): ...
    def search_news(self, query, filters): ...
    def search_images(self, query, filters): ...
    def search_videos(self, query, filters): ...
    def search_reports(self, query, filters): ...
```

Konfiguracja:

```env
WEB_SEARCH_PROVIDER=duckduckgo
WEB_SEARCH_API_KEY=
WEB_SEARCH_RESULT_LIMIT=8
WEB_SEARCH_FRESHNESS_DAYS=7
WEB_SEARCH_CACHE_ENABLED=true
WEB_SEARCH_CACHE_TTL_SECONDS=900
```

Najlepsza kolejnosc:

1. zostawic DuckDuckGo/Wikipedia jako fallback,
2. dodac Brave Search albo SerpAPI jako opcjonalny provider,
3. dodac image search,
4. dodac news search,
5. dodac video/report search.

## Etap 4: Query planner dla aktualnych informacji

Plik:

```txt
src/research_query_planner.py
```

Query planner nie powinien wysylac do internetu surowego pytania. Powinien zbudowac kilka zapytan:

```json
{
  "topic": "Elon Musk",
  "intent": "current_ranking",
  "freshness_required": true,
  "queries": {
    "web": [
      "Elon Musk richest person current ranking",
      "Forbes billionaires real time Elon Musk",
      "Bloomberg Billionaires Index Elon Musk"
    ],
    "images": [
      "Elon Musk official photo",
      "Elon Musk portrait Wikimedia Commons"
    ],
    "reports": [
      "Forbes billionaires list Elon Musk",
      "Bloomberg Billionaires Index Elon Musk"
    ],
    "videos": [
      "Elon Musk interview latest"
    ]
  },
  "filters": {
    "must_include": ["Elon Musk", "Musk"],
    "preferred_domains": ["forbes.com", "bloomberg.com", "reuters.com", "wikipedia.org"],
    "freshness_days": 7
  }
}
```

## Etap 5: Ranking i scoring zrodel

Dodac scoring w:

```txt
src/search_service.py
src/research_orchestrator.py
```

Kazdy wynik powinien dostac:

```txt
topic_match_score
freshness_score
authority_score
source_type_score
cross_confirmation_score
final_confidence
```

Przyklad wag:

```txt
topic_match_score: 0.30
freshness_score: 0.20
authority_score: 0.20
cross_confirmation_score: 0.20
source_type_score: 0.10
```

Przy pytaniach aktualnych:

```txt
wynik z dzisiaj / ostatnich dni -> wysoki freshness_score
wynik sprzed roku -> niski freshness_score
brak daty -> sredni albo niski freshness_score
```

Preferowane zrodla:

```txt
oficjalne strony
agencje informacyjne
instytucje publiczne
uczelnie
raporty firmowe
Forbes/Bloomberg dla rankingow majatkowych
Reuters/AP dla newsow
```

Zrodla slabe:

```txt
losowe blogi
strony bez dat
strony bez autora
strony agregujace cudze teksty
wyniki z tytulem clickbaitowym
```

## Etap 6: Walidacja zgodnosci zrodel

Plik:

```txt
src/llm_validator.py
```

Walidator ma sprawdzac:

1. Czy odpowiedz wynika ze zrodel?
2. Czy zrodla mowia o tym samym temacie?
3. Czy zrodla sa wystarczajaco aktualne?
4. Czy zrodla sa zgodne miedzy soba?
5. Czy sa sprzecznosci?
6. Czy confidence jest wystarczajace?

Format wyniku:

```json
{
  "status": "accepted",
  "confidence": 0.86,
  "reason": "3 niezalezne zrodla potwierdzaja ten sam fakt",
  "contradictions": [],
  "accepted_sources": [
    "https://...",
    "https://..."
  ],
  "rejected_sources": [
    {
      "url": "https://...",
      "reason": "stare dane"
    }
  ]
}
```

Tryby:

```env
LLM_VALIDATOR_ENABLED=false
LLM_VALIDATOR_MODEL=gpt-4.1-mini
LLM_VALIDATOR_MIN_CONFIDENCE=0.72
```

Domyslnie walidator moze dzialac heurystycznie, bez kosztow. LLM validator wlaczamy pozniej, gdy chcemy mocniejsza kontrole.

## Etap 7: Twardy prompt anty-cutoff

Dodac do system promptu albo promptu search:

```txt
Jesli pytanie dotyczy aktualnych informacji, nie odpowiadaj z wiedzy modelu.
Jesli nie dostajesz verified_search_context, powiedz, ze nie masz aktualnych danych.
Nie mow "moja wiedza siega 2024"; uruchom search albo zgloś brak pewnych zrodel.
Odpowiedz musi wskazywac poziom pewnosci, gdy pytanie dotyczy danych zmiennych.
```

Docelowe zachowanie:

```txt
Uzytkownik: Kto jest teraz najbogatszy na swiecie?
JARVIS: Sprawdzam aktualne zrodla.
JARVIS: Wedlug zweryfikowanych zrodel X jest obecnie na pierwszym miejscu. Pewnosc: wysoka/srednia. Zrodla: ...
```

## Etap 8: Zdjecia - osobny pipeline walidacji

Plik:

```txt
src/media_filters.py
```

Zdjecia nie moga byc dobierane tylko po pierwszym `image_url`.

Pipeline:

```txt
topic
-> image query planner
-> kandydaci zdjec
-> filtr techniczny
-> filtr semantyczny
-> ranking
-> display
```

Filtr techniczny:

```txt
ma image_url
ma page_url albo source_url
nie jest placeholderem
nie jest ikona/logo, jesli pytanie dotyczy osoby
nie jest duplikatem
ma sensowne wymiary, jesli provider je zwraca
```

Filtr semantyczny:

```txt
caption zawiera temat lub alias
page title zawiera temat lub alias
page_url zawiera temat lub wiarygodna domene
source jest zgodny z tematem
jesli temat to osoba, obraz nie moze wskazywac innej osoby
```

Preferowane zrodla zdjec:

```txt
Wikimedia Commons
Wikipedia thumbnails
oficjalne strony
strony instytucji
agencje informacyjne
publiczne archiwa
```

Wynik:

```json
{
  "image_url": "...",
  "page_url": "...",
  "caption": "Elon Musk portrait",
  "source": "Wikimedia",
  "confidence": 0.91,
  "validation": {
    "status": "accepted",
    "reasons": ["topic_match", "trusted_domain"]
  }
}
```

## Etap 9: VisualBrief jako jedyny kontrakt displaya

Niech UI dostaje tylko jeden spójny format:

```json
{
  "type": "visual_result",
  "mode": "research_brief",
  "topic": "...",
  "title": "...",
  "summary": "...",
  "confidence": 0.84,
  "sources": [],
  "images": [],
  "videos": [],
  "reports": [],
  "claims": [],
  "validation": {},
  "planner_trace": {}
}
```

UI nie ma zgadywac tematu. UI tylko renderuje to, co backend juz zweryfikowal.

## Etap 10: Research trace

Plik:

```txt
data/research_traces.json
```

Kazdy research powinien zapisac:

```json
{
  "question": "...",
  "topic": "...",
  "intent": "...",
  "queries": {},
  "result_count": 8,
  "accepted_sources": [],
  "rejected_sources": [],
  "accepted_images": [],
  "rejected_images": [],
  "confidence": 0.82,
  "validator_status": "accepted",
  "final_mode": "research_brief"
}
```

Dzieki temu bedziemy widziec, dlaczego JARVIS wybral dane zrodlo lub zdjecie.

## Etap 11: Cache z TTL

Obecny cache wyszukiwania jest przydatny, ale dla aktualnych informacji musi miec TTL zalezne od intencji.

Przyklady:

```txt
pogoda: 10 minut
kursy/ceny: 5 minut
news: 15 minut
ranking: 1 godzina
biografia: 24 godziny
zdjecia encyklopedyczne: 7 dni
```

Konfiguracja:

```env
WEB_SEARCH_CACHE_ENABLED=true
WEB_SEARCH_CACHE_TTL_SECONDS=900
```

## Etap 12: UI dla pewnosci i zrodel

Pliki:

```txt
ui/app.js
ui/styles.css
```

Display powinien pokazywac:

```txt
temat
odpowiedz
confidence
status walidacji
zrodla
zdjecia
raporty
filmy
ostrzezenie przy niskiej pewnosci
```

Przy niskiej pewnosci:

```txt
Nie mam wystarczajaco pewnych danych, ale znalazlem nastepujace zrodla do sprawdzenia.
```

## Etap 13: Testy

Dodatkowe testy:

```txt
tests/test_search_service.py
tests/test_research_query_planner.py
tests/test_research_orchestrator.py
tests/test_media_filters.py
tests/test_llm_validator.py
tests/test_web_wake_gate.py
tests/test_ui_dashboard.py
```

Scenariusze:

1. Pytanie aktualne wymusza search.
2. Pytanie historyczne nie wymusza search.
3. Brak zrodel nie pozwala na pewna odpowiedz.
4. Stare zrodla obnizaja confidence.
5. Sprzeczne zrodla obnizaja confidence.
6. Odpowiedz nie moze zawierac "moja wiedza siega 2024".
7. Fake search z blednym tematem nie generuje displaya.
8. Zdjecie innej osoby zostaje odrzucone.
9. UI obsluguje `research_brief`.
10. Wake gate blokuje search bez aktywacji.

## Etap 14: Docelowy flow

```txt
User:
Kto jest teraz najbogatszy na swiecie?

JARVIS:
1. Wykrywa current_ranking.
2. Buduje query plan.
3. Pobiera wyniki z web/news.
4. Odrzuca stare i slabe zrodla.
5. Porownuje wyniki.
6. Liczy confidence.
7. Przekazuje verified_search_context do LLM.
8. LLM odpowiada tylko na podstawie zrodel.
9. Research orchestrator buduje research_brief.
10. Media filters waliduja zdjecia.
11. UI pokazuje display z odpowiedzia, zdjeciami i zrodlami.
```

## Minimalny MVP

Najpierw zrobic:

1. rozszerzone `requires_current_information`,
2. search-before-answer,
3. prompt anty-cutoff,
4. scoring zrodel,
5. confidence w odpowiedzi,
6. test, ze JARVIS nie mowi "moja wiedza siega 2024",
7. test, ze aktualne pytania nie ida do LLM bez searcha.

## Wersja docelowa

Potem dodac:

1. provider Brave/SerpAPI,
2. news search,
3. image search,
4. video search,
5. report search,
6. LLM validator mode,
7. zaawansowany display `research_brief`,
8. pelny trace w UI,
9. ocene pewnosci zrodel,
10. cross-check miedzy kilkoma niezaleznymi zrodlami.

## Kryterium sukcesu

JARVIS dziala poprawnie, jesli:

1. nie odpowiada z nieaktualnej wiedzy na pytania aktualne,
2. nie mowi "moja wiedza siega 2024" jako finalnej odpowiedzi,
3. szuka najnowszych dostepnych zrodel,
4. pokazuje poziom pewnosci,
5. wykrywa sprzecznosci,
6. odrzuca bledne zdjecia,
7. display pokrywa sie z odpowiedzia,
8. caly proces jest widoczny w `research_traces.json`.
