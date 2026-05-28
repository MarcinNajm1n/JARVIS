from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.voice_commands import normalize_voice_command


OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


WEATHER_CODE_DESCRIPTIONS = {
    0: "bezchmurnie",
    1: "glownie bezchmurnie",
    2: "czesciowe zachmurzenie",
    3: "pochmurno",
    45: "mgla",
    48: "mgla osadzajaca szadz",
    51: "lekka mzawka",
    53: "umiarkowana mzawka",
    55: "gesta mzawka",
    61: "lekki deszcz",
    63: "umiarkowany deszcz",
    65: "silny deszcz",
    71: "lekki snieg",
    73: "umiarkowany snieg",
    75: "silny snieg",
    80: "przelotny lekki deszcz",
    81: "przelotny deszcz",
    82: "silna ulewa",
    95: "burza",
    96: "burza z gradem",
    99: "silna burza z gradem",
}


@dataclass(frozen=True)
class WeatherResult:
    ok: bool
    location: str
    lat: float | None = None
    lon: float | None = None
    temperature: float | None = None
    description: str | None = None
    wind: float | None = None
    humidity: float | None = None
    cloud_cover: float | None = None
    observed_at: str | None = None
    source: str = "Open-Meteo"
    error: str | None = None

    def to_visual_payload(self) -> dict[str, Any]:
        weather = {
            "temperature": self.temperature,
            "description": self.description,
            "wind": self.wind,
            "humidity": self.humidity,
            "cloud_cover": self.cloud_cover,
            "observed_at": self.observed_at,
        }
        return {
            "type": "visual_result",
            "mode": "map_weather",
            "presentation": "animated_scene",
            "animation_profile": "result" if self.ok else "low_confidence",
            "ok": self.ok,
            "location": self.location,
            "lat": self.lat,
            "lon": self.lon,
            "weather": weather,
            "sources": [self.source] if self.source else [],
            "cost": {"operation": "weather", "estimated_cost_usd": 0.0},
            "message": self.format_spoken_summary(),
            "error": self.error,
        }

    def format_spoken_summary(self) -> str:
        if not self.ok:
            return f"Nie mam aktualnych danych pogodowych dla: {self.location}."
        temperature = _format_number(self.temperature)
        wind = _format_number(self.wind)
        description = self.description or "brak opisu"
        return (
            f"{self.location}: {temperature} stopni, {description}, "
            f"wiatr {wind} km/h. Bez dramatu, szefie."
        )


def extract_weather_location(text: str) -> str | None:
    normalized = normalize_voice_command(text)
    patterns = (
        r"(?:pogoda|temperature|temperatura|pada|deszcz|wiatr)\s+(?:w|we|dla|na)\s+(.+)$",
        r"(?:jaka|jaki|jakie)\s+(?:jest\s+)?(?:pogoda|temperatura)\s+(?:w|we|dla)\s+(.+)$",
        r"(?:czy\s+)?pada\s+(?:w|we)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return _clean_location(match.group(1))
    return None


def is_weather_query(text: str) -> bool:
    normalized = normalize_voice_command(text)
    return extract_weather_location(text) is not None or any(
        phrase in normalized
        for phrase in (
            "pogoda",
            "temperatura",
            "czy pada",
            "jaki wiatr",
            "zachmurzenie",
        )
    )


def get_current_weather(location: str, timeout: float = 4.0) -> WeatherResult:
    clean_location = _clean_location(location)
    if not clean_location:
        return WeatherResult(False, location or "nieznana lokalizacja", error="Brak lokalizacji.")

    try:
        place = _geocode_location(clean_location, timeout=timeout)
        if place is None:
            return WeatherResult(
                False,
                clean_location.title(),
                error="Nie znaleziono lokalizacji.",
            )

        weather = _fetch_weather(place["lat"], place["lon"], timeout=timeout)
        current = weather.get("current") or {}
        code = int(current.get("weather_code", -1))
        return WeatherResult(
            ok=True,
            location=place["name"],
            lat=float(place["lat"]),
            lon=float(place["lon"]),
            temperature=_as_float(current.get("temperature_2m")),
            description=WEATHER_CODE_DESCRIPTIONS.get(code, f"kod pogody {code}"),
            wind=_as_float(current.get("wind_speed_10m")),
            humidity=_as_float(current.get("relative_humidity_2m")),
            cloud_cover=_as_float(current.get("cloud_cover")),
            observed_at=str(current.get("time") or datetime.now(timezone.utc).isoformat()),
        )
    except Exception as error:
        return WeatherResult(False, clean_location.title(), error=str(error))


def _geocode_location(location: str, timeout: float) -> dict[str, Any] | None:
    params = urllib.parse.urlencode(
        {
            "name": location,
            "count": 1,
            "language": "pl",
            "format": "json",
        }
    )
    data = _fetch_json(f"{OPEN_METEO_GEOCODING_URL}?{params}", timeout=timeout)
    results = data.get("results") or []
    if not results:
        return None
    first = results[0]
    country = first.get("country")
    name = str(first.get("name") or location).strip().title()
    label = f"{name}, {country}" if country else name
    return {"name": label, "lat": first["latitude"], "lon": first["longitude"]}


def _fetch_weather(lat: float, lon: float, timeout: float) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "weather_code",
                    "cloud_cover",
                    "wind_speed_10m",
                ]
            ),
            "wind_speed_unit": "kmh",
        }
    )
    return _fetch_json(f"{OPEN_METEO_FORECAST_URL}?{params}", timeout=timeout)


def _fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-local-ui/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _clean_location(location: str) -> str:
    cleaned = re.sub(r"[?.!,;:]+$", "", location.strip())
    cleaned = re.sub(r"\b(teraz|dzisiaj|jutro|aktualnie|prosze|szefie)\b", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    known_forms = {
        "berlinie": "Berlin",
        "warszawie": "Warszawa",
        "krakowie": "Krakow",
        "poznaniu": "Poznan",
        "wroclawiu": "Wroclaw",
        "gdansku": "Gdansk",
    }
    if cleaned.lower() in known_forms:
        return known_forms[cleaned.lower()]
    return cleaned


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_number(value: float | None) -> str:
    if value is None:
        return "brak danych"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"
