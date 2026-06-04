from __future__ import annotations

from app.models.model_config import ModelConfig


def build_model_config(provider: dict) -> ModelConfig:
    return ModelConfig(
        api_key=provider["api_key"],
        base_url=provider["base_url"],
        provider=provider["name"],
        model_name="",
        name=provider["name"],
    )


def format_model_rows(raw_models: list[dict]) -> list[dict]:
    return [
        {
            "id": model.get("id"),
            "provider_id": model.get("provider_id"),
            "model_name": model.get("model_name"),
            "created_at": model.get("created_at", None),
        }
        for model in raw_models
    ]
