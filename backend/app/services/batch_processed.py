import json
from pathlib import Path
from typing import Callable, Optional

from app.services.note_tasks import SUPPORTED_GENERATION_MODE, delete_task_artifacts
from app.services.task_runtime import default_note_output_dir


def _default_output_dir() -> Path:
    return default_note_output_dir()


def infer_result_mode(result_content: dict | str) -> str:
    if isinstance(result_content, dict):
        mode = result_content.get("mode")
        if mode in {SUPPORTED_GENERATION_MODE, "transcript", "note"}:
            return mode
        markdown = result_content.get("markdown") or ""
    else:
        markdown = result_content

    if "## 校对文字稿" in markdown:
        return "polished_transcript"
    if "## 简体中文文字稿" in markdown:
        return "transcript"
    return "note"


def find_existing_task_id(
    video_id: str,
    mode: Optional[str] = None,
    *,
    output_dir: Path | None = None,
    delete_artifacts: Callable[[str, Path], int] = delete_task_artifacts,
    delete_task_record: Callable[[str], object] | None = None,
) -> Optional[str]:
    note_output_dir = output_dir or _default_output_dir()
    requested_mode = mode or SUPPORTED_GENERATION_MODE
    matched_task_id = None
    for path in note_output_dir.glob("*.json"):
        name = path.name
        if name.endswith(".status.json") or path.stem.endswith("_audio") or path.stem.endswith("_transcript"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (data.get("audio_meta") or {}).get("video_id") != video_id:
            continue
        result_mode = infer_result_mode(data)
        if result_mode != SUPPORTED_GENERATION_MODE:
            delete_artifacts(path.stem, note_output_dir)
            if delete_task_record:
                delete_task_record(path.stem)
            continue
        if requested_mode != SUPPORTED_GENERATION_MODE:
            continue
        if result_mode != requested_mode:
            continue
        if matched_task_id is None:
            matched_task_id = path.stem
    return matched_task_id


def mark_processed_videos(
    videos: list[dict],
    mode: Optional[str] = None,
    *,
    existing_task_lookup: Callable[[str, Optional[str]], Optional[str]] = find_existing_task_id,
) -> list[dict]:
    marked_videos = []
    for video in videos:
        marked_video = dict(video)
        existing_task_id = existing_task_lookup(str(video.get("video_id") or ""), mode)
        if existing_task_id:
            marked_video["processed_task_id"] = existing_task_id
        marked_videos.append(marked_video)
    return marked_videos


def mark_processed_page_items(
    payload: dict,
    mode: Optional[str] = None,
    *,
    existing_task_lookup: Callable[[str, Optional[str]], Optional[str]] = find_existing_task_id,
) -> dict:
    return {
        **payload,
        "items": mark_processed_videos(
            payload.get("items") or [],
            mode,
            existing_task_lookup=existing_task_lookup,
        ),
    }
