from types import SimpleNamespace

from app.services.provider_serialization import (
    mask_api_key,
    provider_to_dict,
    serialize_provider,
)


def _provider(**overrides):
    values = {
        "id": "provider-1",
        "name": "Demo Provider",
        "logo": "custom",
        "type": "openai",
        "api_key": "sk-1234567890",
        "base_url": "https://api.example.test/v1",
        "enabled": 1,
        "created_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_provider_to_dict_preserves_raw_provider_fields():
    assert provider_to_dict(_provider()) == {
        "id": "provider-1",
        "name": "Demo Provider",
        "logo": "custom",
        "type": "openai",
        "api_key": "sk-1234567890",
        "base_url": "https://api.example.test/v1",
        "enabled": 1,
        "created_at": None,
    }


def test_serialize_provider_can_preserve_or_mask_api_key():
    row = _provider(api_key="sk-1234567890")

    assert serialize_provider(row)["api_key"] == "sk-1234567890"
    assert serialize_provider(row, mask_key=True)["api_key"] == "sk-1*****7890"


def test_mask_api_key_keeps_legacy_short_key_behavior():
    assert mask_api_key("") == ""
    assert mask_api_key("abc") == "***"
    assert mask_api_key("12345678") == "12345678"
