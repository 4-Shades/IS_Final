from datetime import date

import httpx

from common.travel_data import GeocodingProvider, PlacesProvider, WeatherProvider


def test_geocoding_provider_returns_metadata_and_caches_lookup() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "nominatim.openstreetmap.org"
        return httpx.Response(
            200,
            json=[
                {
                    "display_name": "Paris, France",
                    "lat": "48.8566",
                    "lon": "2.3522",
                    "address": {"country": "France"},
                }
            ],
        )

    provider = GeocodingProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = provider.lookup("Paris, France")
    assert result is not None
    assert result.latitude == 48.8566
    assert result.longitude == 2.3522
    assert result.country == "France"
    assert result.metadata.provider == "nominatim"
    assert result.metadata.is_live_inventory is False
    assert provider.lookup("Paris, France") == result


def test_places_provider_builds_overpass_query_and_marks_source_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "overpass-api.de"
        body = request.content.decode("utf-8")
        assert "restaurant" in body.lower()
        return httpx.Response(
            200,
            json={
                "elements": [
                    {
                        "type": "node",
                        "id": 101,
                        "lat": 48.8566,
                        "lon": 2.3522,
                        "tags": {"name": "Le Petit Paris", "amenity": "restaurant"},
                    }
                ]
            },
        )

    provider = PlacesProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    results = provider.search(48.8566, 2.3522, "restaurant", radius_km=2)

    assert len(results) == 1
    assert results[0].name == "Le Petit Paris"
    assert results[0].osm_id == "node/101"
    assert results[0].metadata.provider == "overpass"
    assert results[0].metadata.source_url.startswith("https://www.openstreetmap.org/")


def test_weather_provider_exposes_open_meteo_forecast_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.open-meteo.com"
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": ["2026-09-23"],
                    "temperature_2m_max": [24.5],
                    "precipitation_sum": [0.1],
                    "weather_code": [1],
                }
            },
        )

    provider = WeatherProvider(client=httpx.Client(transport=httpx.MockTransport(handler)))
    items = provider.forecast(48.8566, 2.3522, date(2026, 9, 23), date(2026, 9, 23))

    assert len(items) == 1
    assert items[0].temperature_c == 24.5
    assert items[0].metadata.provider == "open-meteo"
    assert items[0].metadata.license == "CC BY 4.0"
    assert items[0].metadata.is_live_inventory is False
