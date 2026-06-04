from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.services.task_runtime import SUPPORTED_GENERATION_MODE, default_note_output_dir


def resolve_note_output_dir(output_dir: Path | str | None = None) -> Path:
    if output_dir is None:
        return default_note_output_dir()
    return Path(output_dir)


def note_result_path(output_dir: Path | str, task_id: str) -> Path:
    return resolve_note_output_dir(output_dir) / f"{task_id}.json"


def note_status_path(output_dir: Path | str, task_id: str) -> Path:
    return resolve_note_output_dir(output_dir) / f"{task_id}.status.json"


def note_markdown_cache_path(output_dir: Path | str, task_id: str) -> Path:
    return resolve_note_output_dir(output_dir) / f"{task_id}_markdown.md"


def task_artifact_paths(task_id: str, output_dir: Path | str) -> list[Path]:
    note_output_dir = resolve_note_output_dir(output_dir)
    return [
        note_output_dir / f"{task_id}.json",
        note_output_dir / f"{task_id}.status.json",
        note_output_dir / f"{task_id}_audio.json",
        note_output_dir / f"{task_id}_transcript.json",
        note_output_dir / f"{task_id}_markdown.md",
    ]


def is_note_result_file(path: Path) -> bool:
    name = path.name
    return (
        path.suffix == ".json"
        and not name.endswith(".status.json")
        and not path.stem.endswith("_transcript")
        and not path.stem.endswith("_audio")
    )


def is_polished_transcript_result(result_content: Mapping[str, Any]) -> bool:
    if result_content.get("mode") == SUPPORTED_GENERATION_MODE:
        return True

    markdown = result_content.get("markdown")
    return isinstance(markdown, str) and "## 校对文字稿" in markdown


def extract_audio_meta(result_content: Mapping[str, Any]) -> dict:
    return result_content.get("audio_meta") or result_content.get("audioMeta") or {}


def build_saved_note_payload(note: Any, mode: str = SUPPORTED_GENERATION_MODE) -> dict:
    payload = asdict(note)
    payload["mode"] = mode
    return payload


def build_edited_markdown_payload(
    result_content: Mapping[str, Any],
    markdown: str,
    *,
    edited_at: datetime | None = None,
    mode: str = SUPPORTED_GENERATION_MODE,
) -> dict:
    edited_content = dict(result_content)
    edited_content["markdown"] = markdown
    edited_content["edited_at"] = (edited_at or datetime.now(timezone.utc)).isoformat()
    edited_content["mode"] = mode
    return edited_content
