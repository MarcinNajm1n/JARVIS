# Animowany display JARVIS

## Cel

Rozszerzyc istniejacy pipeline `VISUAL_RESULT` o domyslnie animowana scene HUD i osobny tryb tabelaryczny tylko dla danych liczbowych, takich jak rachunki, faktury, koszty, budzety i porownania kwot.

## Kontrakt payloadu

Kazdy nowy display moze uzywac opcjonalnych pol:

- `presentation`: `animated_scene` albo `structured_modal`
- `animation_profile`: `searching`, `result`, `critical` albo `low_confidence`
- `structured_data`: dane tabeli uzywane tylko przy `structured_modal`

Stare payloady bez tych pol pozostaja poprawne.

## Zachowanie

- Pytania realtime i research trafiaja do `jarvis_tactical_hud`.
- Pogoda zostaje na dedykowanym `map_weather`.
- Zwykle pytania faktograficzne trafiaja do `entity_profile`, `entity_gallery` albo `research_brief`.
- Pytania o rachunki, faktury, koszty i budzety trafiaja do `structured_modal`.
- Odpowiedzi o niskiej pewnosci dostaja `animation_profile: low_confidence`, zamiast udawac pewny wynik.

## Testy akceptacyjne

- Zwykly factual answer nie dostaje `structured_modal`.
- Rachunki/faktury/koszty dostaja `presentation: structured_modal`.
- HUD realtime zachowuje `presentation: animated_scene`.
- Pogoda nadal renderuje `map_weather`.
- UI zawiera renderer `renderStructuredModal`.
- Animacje nadal respektuja `prefers-reduced-motion` i `JARVIS_HUD_ANIMATIONS_ENABLED=false`.

## Po zmianach

Po wiekszej iteracji displayu warto odswiezyc graf projektu:

```powershell
graphify .
```
