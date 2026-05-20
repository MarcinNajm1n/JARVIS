from pathlib import Path

from src import web_app


ROOT = Path(__file__).resolve().parents[1]


def test_ui_zawiera_panele_kokpitu_jarvisa():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")

    assert 'id="statusPanel"' in html
    assert 'id="wakeTranscript"' in html
    assert 'id="taskPanel"' in html
    assert 'id="projectPanel"' in html
    assert 'id="memoryPanel"' in html
    assert 'id="llmGate"' in html
    assert 'id="systemsPanel"' in html
    assert 'id="costMeter"' in html
    assert 'id="tokenMeter"' in html
    assert 'id="briefingPanel"' in html
    assert 'id="setupWarning"' in html
    assert 'id="resultPanel"' in html
    assert 'id="resultMap"' in html
    assert 'id="eventQueue"' in html
    assert 'id="resultHistory"' in html
    assert 'id="commandPalette"' in html
    assert '<strong id="costMeter"' in html
    assert html.index('class="top-cost-meter"') < html.index('<main class="stage"')
    assert html.index('id="costMeter"') < html.index('class="core-wrap"')
    assert html.index('id="costMeter"') < html.index('id="transcript"')
    assert "leaflet@1.9.4/dist/leaflet.css" in html
    assert "leaflet@1.9.4/dist/leaflet.js" in html
    assert 'id="leafletMap"' in html
    assert 'id="resultImage"' in html
    assert "styles.css?v=17" in html
    assert "app.js?v=17" in html


def test_ui_obsluguje_dashboard_i_prywatnosc():
    js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")

    assert "renderDashboard" in js
    assert "clear_transcripts" in js
    assert "history_toggle" in js
    assert "LLM BLOCKED" in js
    assert "LLM ACTIVE" in js
    assert "SHUTDOWN" in js
    assert "window.close" in js
    assert "setup_warnings" in js
    assert "estimated_cost_usd" in js
    assert "costMeter.textContent" in js
    assert "tokenMeter.textContent" in js
    assert "last_intent" in js
    assert "wake_detector" in js
    assert "renderVisualResult" in js
    assert "renderWeatherResult" in js
    assert "renderEntityProfile" in js
    assert "renderEmbeddedOsmMap" in js
    assert "openstreetmap.org/export/embed.html" in js
    assert "activateVisualScene" in js
    assert "renderRelatedResults" in js
    assert "map_weather" in js
    assert "entity_profile" in js
    assert "L.tileLayer" in js
    assert "VISUAL_RESULT" in js
    assert "UI_EVENT" in js
    assert "DISPLAYING_RESULT" in js
    assert "visualHistory" in js
    assert "commandPalette" in js


def test_ui_ma_style_paneli_kokpitu():
    css = (ROOT / "ui" / "styles.css").read_text(encoding="utf-8")

    assert ".cockpit" in css
    assert ".cockpit {\n  position: relative;" in css
    assert ".cockpit {\n  position: fixed;" not in css
    assert ".stage {\n  position: relative;\n  display: grid;" in css
    assert 'grid-template-areas: "left center right";' in css
    assert "var(--panel-orbit-gap)" in css
    assert "--panel-orbit-gap: clamp(" in css
    assert "350px" in css
    assert "overflow-x: hidden;" in css
    assert "overflow-y: auto;" in css
    assert ".cockpit {\n  position: relative;" in css
    assert "max-height: none;" in css
    assert "overflow: visible;" in css
    assert "#taskPanel {\n  max-height: none;" in css
    assert "#memoryPanel {\n  max-height: none;" in css
    assert "overflow: auto;" not in css
    assert ".left-panel {\n  grid-area: left;" in css
    assert ".right-panel {\n  grid-area: right;" in css
    assert "--left-panel-width: clamp(208px, 12.5vw, 240px);" in css
    assert "--right-panel-width: clamp(256px, 15.84vw, 304px);" in css
    assert "#llmGate" in css
    assert "#memoryPanel" in css
    assert ".top-cost-meter" in css
    assert "--api-banner-width: clamp(180px, 14.4vw, 252px);" in css
    assert "--api-banner-center-y: clamp(72px, calc(25vh" in css
    assert "top: var(--api-banner-center-y);" in css
    assert "left: 50%;" in css
    assert "width: var(--api-banner-width);" in css
    assert "padding: 8px 12px;" in css
    assert "@media (max-width: 1040px)" in css
    assert ".cost-meter" not in css
    assert ".core-wrap {\n  grid-area: center;\n  position: relative;" in css
    assert ".hud {\n  position: fixed;" in css
    assert "justify-self: center;" in css
    assert "overflow-wrap: anywhere;" in css
    assert "font-size: clamp(0.75rem" in css
    assert "#transcript {\n  order: 3;" in css
    assert "#textForm {\n  order: 6;" in css
    assert ".setup-warning" in css
    assert ".result-panel" in css
    assert ".result-map" in css
    assert ".leaflet-map" in css
    assert ".leaflet-ready" in css
    assert ".osm-embed" in css
    assert ".map-hero-image" in css
    assert ".scene-enter" in css
    assert "scene-materialize" in css
    assert "image-reveal" in css
    assert ".result-image" in css
    assert ".event-queue" in css
    assert ".command-palette" in css
    assert 'body[data-state="searching"]' in css
    assert 'body[data-state="displaying_result"]' in css


def test_favicon_route_nie_zwraca_404():
    response = web_app.favicon()

    assert response.status_code == 204
