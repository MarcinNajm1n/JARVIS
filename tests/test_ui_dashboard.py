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
    assert 'id="costPanel"' in html
    assert 'id="costMeter"' in html
    assert 'id="briefingPanel"' in html
    assert 'id="setupWarning"' in html


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
    assert "last_intent" in js
    assert "wake_detector" in js


def test_ui_ma_style_paneli_kokpitu():
    css = (ROOT / "ui" / "styles.css").read_text(encoding="utf-8")

    assert ".cockpit" in css
    assert "#llmGate" in css
    assert "#memoryPanel" in css
    assert ".cost-meter" in css
    assert ".setup-warning" in css


def test_favicon_route_nie_zwraca_404():
    response = web_app.favicon()

    assert response.status_code == 204
