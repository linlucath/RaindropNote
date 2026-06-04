import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from app.enmus.task_status_enums import TaskStatus
from app.services.progress_summary import (
    build_summary,
    group_items_by_status,
    parse_iso,
    summary_bucket,
)
from app.services.task_runtime import (
    ACTIVE_BATCH_STATUSES,
    ACTIVE_TASK_STATUSES,
    TERMINAL_BATCH_STATUSES,
    TERMINAL_TASK_STATUSES,
)


INTERMEDIATE_TASK_SUFFIXES = ("_markdown", "_audio", "_transcript")


def safe_read_json(path: Path) -> Optional[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def is_intermediate_task_id(task_id: str) -> bool:
    return task_id.endswith(INTERMEDIATE_TASK_SUFFIXES)


def result_file_for_task(note_output_dir: Path, task_id: str) -> Path:
    return note_output_dir / f"{task_id}.json"


def infer_task_title(status_payload: dict, result_payload: Optional[dict]) -> str:
    if status_payload.get("title"):
        return status_payload["title"]
    if result_payload:
        audio_meta = result_payload.get("audio_meta") or {}
        return audio_meta.get("title") or ""
    return ""


def infer_task_platform(status_payload: dict, result_payload: Optional[dict]) -> str:
    if status_payload.get("platform"):
        return status_payload["platform"]
    if result_payload:
        audio_meta = result_payload.get("audio_meta") or {}
        return audio_meta.get("platform") or ""
    return ""


def build_task_item(task_id: str, status_payload: dict, result_payload: Optional[dict]) -> dict:
    status = status_payload.get("status")
    return {
        "id": task_id,
        "task_id": task_id,
        "title": infer_task_title(status_payload, result_payload),
        "platform": infer_task_platform(status_payload, result_payload),
        "status": status,
        "message": status_payload.get("message", ""),
        "created_at": status_payload.get("created_at"),
        "updated_at": status_payload.get("updated_at"),
        "has_result": result_payload is not None,
    }


def normalize_stale_cancelling_task(
    task_id: str,
    status_payload: dict,
    *,
    note_output_dir: Path,
    stale_cancelling_after_seconds: int,
    write_status: Callable[..., dict],
) -> dict:
    if status_payload.get("status") != TaskStatus.CANCELLING.value:
        return status_payload

    updated_at = parse_iso(status_payload.get("updated_at"))
    stale_after = timedelta(seconds=stale_cancelling_after_seconds)
    if datetime.now(timezone.utc) - updated_at < stale_after:
        return status_payload

    return write_status(
        task_id=task_id,
        output_dir=note_output_dir,
        status=TaskStatus.CANCELLED,
        message=status_payload.get("message") or "任务已取消",
        title=status_payload.get("title"),
        platform=status_payload.get("platform"),
    )


def load_task_items(
    note_output_dir: Path,
    *,
    stale_cancelling_after_seconds: int,
    write_status: Callable[..., dict],
) -> list[dict]:
    task_items: dict[str, dict] = {}
    note_output_dir.mkdir(parents=True, exist_ok=True)

    for status_path in note_output_dir.glob("*.status.json"):
        task_id = status_path.name[:-12]
        if is_intermediate_task_id(task_id):
            continue
        status_payload = safe_read_json(status_path)
        if not status_payload:
            continue
        status_payload = normalize_stale_cancelling_task(
            task_id,
            status_payload,
            note_output_dir=note_output_dir,
            stale_cancelling_after_seconds=stale_cancelling_after_seconds,
            write_status=write_status,
        )
        result_payload = safe_read_json(result_file_for_task(note_output_dir, task_id))
        task_items[task_id] = build_task_item(task_id, status_payload, result_payload)

    for result_path in note_output_dir.glob("*.json"):
        name = result_path.name
        if name.endswith(".status.json") or is_intermediate_task_id(result_path.stem):
            continue

        task_id = result_path.stem
        if task_id in task_items:
            continue

        result_payload = safe_read_json(result_path)
        if not result_payload:
            continue

        audio_meta = result_payload.get("audio_meta") or {}
        stat = result_path.stat()
        timestamp = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        task_items[task_id] = {
            "id": task_id,
            "task_id": task_id,
            "title": audio_meta.get("title") or "",
            "platform": audio_meta.get("platform") or "",
            "status": TaskStatus.SUCCESS.value,
            "message": "",
            "created_at": timestamp,
            "updated_at": timestamp,
            "has_result": True,
        }

    return list(task_items.values())


def load_batch_items(batch_output_dir: Path) -> list[dict]:
    batches: list[dict] = []
    if not batch_output_dir.exists():
        return batches

    for batch_path in batch_output_dir.glob("*.json"):
        payload = safe_read_json(batch_path)
        if not payload:
            continue
        batches.append(payload)
    return batches


def build_overview(
    *,
    note_output_dir: Path,
    batch_output_dir: Path,
    stale_cancelling_after_seconds: int,
    write_status: Callable[..., dict],
    recent_terminal_limit: int,
) -> dict:
    tasks = load_task_items(
        note_output_dir,
        stale_cancelling_after_seconds=stale_cancelling_after_seconds,
        write_status=write_status,
    )
    batches = load_batch_items(batch_output_dir)

    task_active, task_terminal = group_items_by_status(
        tasks,
        active_statuses=ACTIVE_TASK_STATUSES,
        terminal_statuses=TERMINAL_TASK_STATUSES,
    )
    batch_active, batch_terminal = group_items_by_status(
        batches,
        active_statuses=ACTIVE_BATCH_STATUSES,
        terminal_statuses=TERMINAL_BATCH_STATUSES,
    )

    return {
        "summary": build_summary(task_active + task_terminal + batch_active + batch_terminal),
        "tasks": {
            "active": task_active,
            "recent_terminal": task_terminal[:recent_terminal_limit],
        },
        "batches": {
            "active": batch_active,
            "recent_terminal": batch_terminal[:recent_terminal_limit],
        },
    }
