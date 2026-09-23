from shared.config import get_settings


def test_settings_include_phase_b_rollout_flags(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OPEN_TRAVEL_DATA_ENABLED", "true")
    monkeypatch.setenv("WEATHER_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("PLACES_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("GROUND_TRANSPORT_ENABLED", "false")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "all-minilm")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("DOWNSTREAM_TIMEOUT_SECONDS", "30")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.llm_provider == "ollama"
    assert settings.open_travel_data_enabled is True
    assert settings.weather_provider_enabled is True
    assert settings.places_provider_enabled is True
    assert settings.ground_transport_enabled is False
    assert settings.ollama_base_url == "http://ollama:11434"
    assert settings.ollama_model == "llama3.2:3b"
