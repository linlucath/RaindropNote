import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

try:
    from app.utils.logger import get_logger

    logger = get_logger(__name__)
except Exception:  # pragma: no cover - fallback for isolated import tests
    import logging

    logger = logging.getLogger(__name__)


def default_llm_cache_enabled() -> bool:
    return os.getenv("LLM_CACHE_ENABLED", "1").lower() not in {"0", "false", "no"}


def default_llm_cache_dir() -> Path:
    return Path(
        os.getenv(
            "LLM_CACHE_DIR",
            str(Path(__file__).resolve().parents[3] / ".cache" / "llm"),
        )
    )


@dataclass
class LlmCache:
    client: object
    model: str
    temperature: float
    cache_dir: Path
    enabled: bool = True

    @staticmethod
    def build_cached_response(content: str):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            from_cache=True,
        )

    def provider_base_url(self) -> str | None:
        base_url = getattr(self.client, "base_url", None)
        if base_url is None and hasattr(self.client, "_base_url"):
            base_url = getattr(self.client, "_base_url")
        return str(base_url) if base_url else None

    def cache_key(self, messages: list) -> str:
        payload = {
            "version": 1,
            "provider_base_url": self.provider_base_url(),
            "model": self.model,
            "temperature": self.temperature,
            "messages": messages,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"

    @staticmethod
    def key_preview(cache_key: str) -> str:
        return cache_key[:12]

    def load(self, cache_key: str):
        if not self.enabled:
            logger.info(
                "LLM cache bypassed: reason=disabled key=%s model=%s provider=%s",
                self.key_preview(cache_key),
                self.model,
                self.provider_base_url(),
            )
            return None

        path = self.path(cache_key)
        if not path.exists():
            logger.info(
                "LLM cache miss: reason=not_found key=%s path=%s",
                self.key_preview(cache_key),
                path,
            )
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(
                "LLM cache invalid_json: key=%s path=%s error=%s; removing cache file",
                self.key_preview(cache_key),
                path,
                exc,
            )
            path.unlink(missing_ok=True)
            return None

        content = payload.get("content")
        if not isinstance(content, str):
            logger.warning(
                "LLM cache invalid_payload: key=%s path=%s content_type=%s; removing cache file",
                self.key_preview(cache_key),
                path,
                type(content).__name__,
            )
            path.unlink(missing_ok=True)
            return None

        logger.info(
            "LLM cache hit: key=%s path=%s content_chars=%d",
            self.key_preview(cache_key),
            path,
            len(content),
        )
        return self.build_cached_response(content)

    def save(self, cache_key: str, content: str) -> None:
        if not self.enabled:
            return

        if not isinstance(content, str) or not content.strip():
            logger.info(
                "LLM cache skip_save: key=%s reason=empty_or_non_string content_type=%s",
                self.key_preview(cache_key),
                type(content).__name__,
            )
            return

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.path(cache_key)
        payload = {
            "version": 1,
            "provider_base_url": self.provider_base_url(),
            "model": self.model,
            "temperature": self.temperature,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)
        logger.info(
            "LLM cache saved: key=%s path=%s content_chars=%d",
            self.key_preview(cache_key),
            path,
            len(content),
        )
