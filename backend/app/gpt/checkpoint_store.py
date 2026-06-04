import json
from datetime import datetime, timezone
from pathlib import Path


def checkpoint_path(checkpoint_dir: Path | str, checkpoint_key: str) -> Path:
    checkpoint_dir = Path(checkpoint_dir)
    safe_key = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in checkpoint_key)
    return checkpoint_dir / f"{safe_key}.gpt.checkpoint.json"


def load_checkpoint(
    checkpoint_dir: Path | str,
    checkpoint_key: str,
    source_signature: str,
) -> dict | None:
    path = checkpoint_path(checkpoint_dir, checkpoint_key)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("source_signature") != source_signature:
            path.unlink(missing_ok=True)
            return None
        return data
    except Exception:
        path.unlink(missing_ok=True)
        return None


def save_checkpoint(
    checkpoint_dir: Path | str,
    checkpoint_key: str,
    source_signature: str,
    partials: list,
    phase: str,
    *,
    updated_at: datetime | None = None,
) -> None:
    path = checkpoint_path(checkpoint_dir, checkpoint_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "source_signature": source_signature,
        "phase": phase,
        "partials": partials,
        "updated_at": (updated_at or datetime.now(timezone.utc)).isoformat(),
    }
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def clear_checkpoint(checkpoint_dir: Path | str, checkpoint_key: str) -> None:
    checkpoint_path(checkpoint_dir, checkpoint_key).unlink(missing_ok=True)
