from src.weather_service import WeatherResult, extract_weather_location, is_weather_query


def test_weather_query_wyciaga_lokalizacje():
    assert extract_weather_location("Jaka jest pogoda w Berlinie?") == "Berlin"
    assert extract_weather_location("czy pada w Berlinie") == "Berlin"
    assert is_weather_query("temperatura w Warszawie") is True


def test_weather_result_formatuje_visual_payload():
    result = WeatherResult(
        ok=True,
        location="Berlin",
        lat=52.52,
        lon=13.405,
        temperature=18,
        description="pochmurno",
        wind=12,
        humidity=61,
        cloud_cover=80,
        observed_at="2026-05-20T12:00",
    )

    payload = result.to_visual_payload()

    assert payload["type"] == "visual_result"
    assert payload["mode"] == "map_weather"
    assert payload["presentation"] == "animated_scene"
    assert payload["animation_profile"] == "result"
    assert payload["location"] == "Berlin"
    assert payload["weather"]["temperature"] == 18
    assert payload["cost"]["estimated_cost_usd"] == 0.0
    assert "Berlin: 18 stopni" in payload["message"]


def test_weather_result_brak_danych_mowi_nie_mam_aktualnych_danych():
    result = WeatherResult(False, "Atlantyda", error="Nie znaleziono lokalizacji.")

    payload = result.to_visual_payload()

    assert payload["ok"] is False
    assert payload["animation_profile"] == "low_confidence"
    assert "Nie mam aktualnych danych pogodowych" in payload["message"]
