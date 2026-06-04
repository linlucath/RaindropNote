from app.services.model_serialization import build_model_config, format_model_rows


def test_format_model_rows_keeps_legacy_shape_and_created_at_default():
    assert format_model_rows([
        {"id": 1, "provider_id": "provider-a", "model_name": "model-a"},
        {
            "id": 2,
            "provider_id": "provider-b",
            "model_name": "model-b",
            "created_at": "2026-06-02T00:00:00",
        },
    ]) == [
        {
            "id": 1,
            "provider_id": "provider-a",
            "model_name": "model-a",
            "created_at": None,
        },
        {
            "id": 2,
            "provider_id": "provider-b",
            "model_name": "model-b",
            "created_at": "2026-06-02T00:00:00",
        },
    ]


def test_build_model_config_uses_provider_name_for_legacy_provider_and_name_fields():
    config = build_model_config({
        "name": "Demo Provider",
        "api_key": "sk-demo",
        "base_url": "https://api.example.test/v1",
    })

    assert config.api_key == "sk-demo"
    assert config.base_url == "https://api.example.test/v1"
    assert config.provider == "Demo Provider"
    assert config.name == "Demo Provider"
    assert config.model_name == ""
