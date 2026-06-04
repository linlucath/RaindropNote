import json
from pathlib import Path
from typing import Any, Optional


def _load_task_result(task_id: str, output_dir: str | Path) -> Optional[dict[str, Any]]:
    result_path = Path(output_dir) / f"{task_id}.json"
    if not result_path.exists():
        return None
    try:
        return json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_favorite_note(result: dict[str, Any]) -> dict[str, Any]:
    audio_meta = result.get("audio_meta") or result.get("audioMeta") or {}
    markdown = result.get("markdown") or ""
    return {
        "title": audio_meta.get("title") or "未命名文字稿",
        "video_id": audio_meta.get("video_id"),
        "platform": audio_meta.get("platform"),
        "markdown": markdown,
        "content": markdown,
        "transcript": result.get("transcript"),
        "audio_meta": audio_meta,
    }


def load_favorite_note(task_id: str, output_dir: str | Path) -> Optional[dict[str, Any]]:
    result = _load_task_result(task_id, output_dir)
    if result is None:
        return None

    return build_favorite_note(result)
