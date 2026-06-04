from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder


def provider_to_dict(provider: Any) -> dict[str, Any]:
    return {
        "id": provider.id,
        "name": provider.name,
        "logo": provider.logo,
        "type": provider.type,
        "api_key": provider.api_key,
        "base_url": provider.base_url,
        "enabled": provider.enabled,
        "created_at": provider.created_at,
    }


def mask_api_key(key: str) -> str:
    if not key or len(key) < 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def serialize_provider(row: Any, *, mask_key: bool = False) -> dict[str, Any] | None:
    if not row:
        return None

    provider = provider_to_dict(row)
    api_key = provider.get("api_key")
    if mask_key:
        api_key = mask_api_key(api_key)

    return {
        "id": provider.get("id"),
        "name": provider.get("name"),
        "logo": provider.get("logo"),
        "type": provider.get("type"),
        "enabled": provider.get("enabled"),
        "base_url": provider.get("base_url"),
        "api_key": api_key,
        "created_at": jsonable_encoder(provider.get("created_at")),
    }
