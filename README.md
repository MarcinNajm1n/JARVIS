# JARVIS — prywatny asystent AI w Pythonie

Projekt edukacyjny: prywatny asystent tekstowy inspirowany J.A.R.V.I.S.-em.

Na obecnym etapie projekt działa w terminalu i obsługuje:
- komunikację z modelem OpenAI,
- prompt systemowy,
- historię rozmowy,
- pamięć stałą sterowaną komendami,
- lokalny zapis danych w plikach JSON,
- podstawowe komendy terminalowe,
- testy jednostkowe modułów pamięci.

## Aktualna architektura

```txt
main.py
→ główna pętla programu

src/command_handler.py
→ obsługa komend użytkownika

src/llm_client.py
→ połączenie z OpenAI API

src/memory_store.py
→ zapis i odczyt historii rozmowy

src/long_term_memory.py
→ zapis i odczyt pamięci stałej

config.py
→ konfiguracja projektu

Można skopiować plik `.env.example` do `.env` i uzupełnić własny klucz API.