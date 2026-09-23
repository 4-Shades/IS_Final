"""Open-travel-data provider adapters for geocoding, POIs, and weather.

These adapters intentionally do not present any result as live availability or a
bookable fare. They provide non-live contextual data with clear provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx


@dataclass(frozen=True)
class ProviderMetadata:
    provider: str
    source_url: str | None = None
    retrieved_at: datetime | None = None
    license: str | None = None
    cache_expires_at: datetime | None = None
    is_live_inventory: bool = False


@dataclass(frozen=True)
class GeocodingResult:
    display_name: str
    latitude: float
    longitude: float
    country: str | None = None
    metadata: ProviderMetadata = field(default_factory=lambda: ProviderMetadata(provider="nominatim"))


@dataclass(frozen=True)
class PlaceResult:
    name: str
    category: str
    latitude: float
    longitude: float
    osm_id: str
    source_url: str
    metadata: ProviderMetadata = field(default_factory=lambda: ProviderMetadata(provider="overpass"))


@dataclass(frozen=True)
class WeatherForecast:
    forecast_date: date
    temperature_c: float | None
    precipitation_mm: float | None
    weather_code: int | None
    metadata: ProviderMetadata = field(default_factory=lambda: ProviderMetadata(provider="open-meteo", license="CC BY 4.0"))


class GeocodingProvider:
    """Nominatim-compatible geocoding provider with minimal local caching."""

    def __init__(self, *, client: httpx.Client | None = None, timeout_seconds: float = 15.0) -> None:
        self.client = client or httpx.Client(timeout=timeout_seconds)
        self.timeout_seconds = timeout_seconds
        self._cache: dict[str, GeocodingResult] = {}

    def lookup(self, query: str) -> GeocodingResult | None:
        key = " ".join(query.strip().split()).lower()
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        params = {
            "q": query,
            "limit": "1",
            "format": "jsonv2",
            "addressdetails": "1",
        }
        response = self.client.get("https://nominatim.openstreetmap.org/search", params=params)
        response.raise_for_status()
        payload = response.json()
        if not payload:
            return None

        item = payload[0]
        result = GeocodingResult(
            display_name=item.get("display_name", query),
            latitude=float(item["lat"]),
            longitude=float(item["lon"]),
            country=(item.get("address") or {}).get("country"),
            metadata=ProviderMetadata(
                provider="nominatim",
                source_url="https://nominatim.openstreetmap.org/ui/search.html?q=" + query.replace(" ", "+"),
                retrieved_at=datetime.now(timezone.utc),
                license="ODbL 1.0",
                cache_expires_at=datetime.now(timezone.utc),
                is_live_inventory=False,
            ),
        )
        self._cache[key] = result
        return result


class PlacesProvider:
    """Overpass POI provider for activities and stay-adjacent local discovery."""

    def __init__(self, *, client: httpx.Client | None = None, timeout_seconds: float = 15.0) -> None:
        self.client = client or httpx.Client(timeout=timeout_seconds)
        self.timeout_seconds = timeout_seconds

    def search(self, latitude: float, longitude: float, category: str, radius_km: float = 5.0, limit: int = 10) -> list[PlaceResult]:
        radius_m = max(1, int(radius_km * 1000))
        query = (
            f"[out:json][timeout:25];"
            f"("
            f"node[\"amenity\"=\"{category}\"](around:{radius_m},{latitude},{longitude});"
            f"way[\"amenity\"=\"{category}\"](around:{radius_m},{latitude},{longitude});"
            f"relation[\"amenity\"=\"{category}\"](around:{radius_m},{latitude},{longitude});"
            f");"
            "out center "
            f"{limit};"
        )
        response = self.client.post("https://overpass-api.de/api/interpreter", data={"data": query})
        response.raise_for_status()
        payload = response.json()
        results: list[PlaceResult] = []
        for element in payload.get("elements", [])[:limit]:
            tags = element.get("tags", {}) or {}
            name = tags.get("name") or tags.get("amenity") or category.title()
            lat = element.get("lat")
            lon = element.get("lon")
            if lat is None or lon is None:
                center = element.get("center") or {}
                lat = center.get("lat")
                lon = center.get("lon")
            if lat is None or lon is None:
                continue
            osm_type = element.get("type", "node")
            osm_id = element.get("id")
            osm_ref = f"{osm_type}/{osm_id}"
            metadata = ProviderMetadata(
                provider="overpass",
                source_url=f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
                retrieved_at=datetime.now(timezone.utc),
                license="ODbL 1.0",
                cache_expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
                is_live_inventory=False,
            )
            results.append(
                PlaceResult(
                    name=name,
                    category=category,
                    latitude=float(lat),
                    longitude=float(lon),
                    osm_id=osm_ref,
                    source_url=metadata.source_url,
                    metadata=metadata,
                )
            )
        return results


class WeatherProvider:
    """Open-Meteo weather provider returning a bounded forecast window."""

    def __init__(self, *, client: httpx.Client | None = None, timeout_seconds: float = 15.0) -> None:
        self.client = client or httpx.Client(timeout=timeout_seconds)
        self.timeout_seconds = timeout_seconds

    def forecast(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> list[WeatherForecast]:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_max,precipitation_sum,weather_code",
            "timezone": "auto",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        response = self.client.get("https://api.open-meteo.com/v1/forecast", params=params)
        response.raise_for_status()
        payload = response.json()

        days = payload.get("daily", {})
        times = days.get("time", [])
        temperatures = days.get("temperature_2m_max", [])
        precipitations = days.get("precipitation_sum", [])
        weather_codes = days.get("weather_code", [])

        metadata = ProviderMetadata(
            provider="open-meteo",
            source_url="https://open-meteo.com/",
            retrieved_at=datetime.now(timezone.utc),
            license="CC BY 4.0",
            cache_expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
            is_live_inventory=False,
        )

        forecast_items: list[WeatherForecast] = []
        for index, date_value in enumerate(times):
            temperature = temperatures[index] if index < len(temperatures) else None
            precipitation = precipitations[index] if index < len(precipitations) else None
            weather_code = weather_codes[index] if index < len(weather_codes) else None
            forecast_items.append(
                WeatherForecast(
                    forecast_date=date.fromisoformat(date_value),
                    temperature_c=float(temperature) if temperature is not None else None,
                    precipitation_mm=float(precipitation) if precipitation is not None else None,
                    weather_code=int(weather_code) if weather_code is not None else None,
                    metadata=metadata,
                )
            )
        return forecast_items
