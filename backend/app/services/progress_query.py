import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.enmus.task_status_enums import TaskStatus


NOTE_OUTPUT_DIR = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
BATCH_OUTPUT_DIR = NOTE_OUTPUT_DIR / "batches"
ACTIVE_TASK_STATUSES = {
    TaskStatus.PENDING.value,
    TaskStatus.PARSING.value,
    TaskStatus.DOWNLOADING.value,
    TaskStatus.TRANSCRIBING.value,
    TaskStatus.SUMMARIZING.value,
    TaskStatus.FORMATTING.value,
    TaskStatus.SAVING.value,
    TaskStatus.CANCELLING.value,
}
ACTIVE_BATCH_STATUSES = {
    TaskStatus.PENDING.value,
    "RUNNING",
    TaskStatus.CANCELLING.value,
}
TERMINAL_TASK_STATUSES = {
    TaskStatus.SUCCESS.value,
    TaskStatus.FAILED.value,
    TaskStatus.CANCELLED.value,
}
TERMINAL_BATCH_STATUSES = {
    TaskStatus.SUCCESS.value,
    TaskStatus.FAILED.value,
    TaskStatus.CANCELLED.value,
}
RECENT_TERMINAL_LIMIT = 20


def _safe_read_json(path: Path) -> Optional[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _parse_iso(value: Optional[str]) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _result_file_for_task(task_id: str) -> Path:
    return NOTE_OUTPUT_DIR / f"{task_id}.json"


def _infer_task_title(status_payload: dict, result_payload: Optional[dict]) -> str:
    if status_payload.get("title"):
        return status_payload["title"]
    if result_payload:
        audio_meta = result_payload.get("audio_meta") or {}
        return audio_meta.get("title") or ""
    return ""


def _infer_task_platform(status_payload: dict, result_payload: Optional[dict]) -> str:
    if status_payload.get("platform"):
        return status_payload["platform"]
    if result_payload:
        audio_meta = result_payload.get("audio_meta") or {}
        return audio_meta.get("platform") or ""
    return ""


def _build_task_item(task_id: str, status_payload: dict, result_payload: Optional[dict]) -> dict:
    status = status_payload.get("status")
    return {
        "id": task_id,
        "task_id": task_id,
        "title": _infer_task_title(status_payload, result_payload),
        "platform": _infer_task_platform(status_payload, result_payload),
        "status": status,
        "message": status_payload.get("message", ""),
        "created_at": status_payload.get("created_at"),
        "updated_at": status_payload.get("updated_at"),
        "has_result": result_payload is not None,
    }


def _load_tasks() -> list[dict]:
    task_items: dict[str, dict] = {}
    NOTE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for status_path in NOTE_OUTPUT_DIR.glob("*.status.json"):
        task_id = status_path.name[:-12]
        if task_id.endswith("_markdown"):
            continue
        status_payload = _safe_read_json(status_path)
        if not status_payload:
            continue
        result_payload = _safe_read_json(_result_file_for_task(task_id))
        task_items[task_id] = _build_task_item(task_id, status_payload, result_payload)

    for result_path in NOTE_OUTPUT_DIR.glob("*.json"):
        name = result_path.name
        if name.endswith(".status.json") or result_path.stem.endswith("_audio") or result_path.stem.endswith("_transcript"):
            continue

        task_id = result_path.stem
        if task_id in task_items:
            continue

        result_payload = _safe_read_json(result_path)
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


def _load_batches() -> list[dict]:
    batches: list[dict] = []
    if not BATCH_OUTPUT_DIR.exists():
        return batches

    for batch_path in BATCH_OUTPUT_DIR.glob("*.json"):
        payload = _safe_read_json(batch_path)
        if not payload:
            continue
        batches.append(payload)
    return batches


def _summary_bucket(status: str) -> str:
    if status == TaskStatus.PENDING.value:
        return "pending"
    if status == TaskStatus.CANCELLING.value:
        return "cancelling"
    if status == TaskStatus.SUCCESS.value:
        return "success"
    if status == TaskStatus.FAILED.value:
        return "failed"
    if status == TaskStatus.CANCELLED.value:
        return "cancelled"
    return "running"


def build_progress_overview() -> dict:
    tasks = _load_tasks()
    batches = _load_batches()
    summary = {
        "pending": 0,
        "running": 0,
        "cancelling": 0,
        "success": 0,
        "failed": 0,
        "cancelled": 0,
    }

    task_active = [task for task in tasks if task["status"] in ACTIVE_TASK_STATUSES]
    task_terminal = [task for task in tasks if task["status"] in TERMINAL_TASK_STATUSES]
    batch_active = [batch for batch in batches if batch.get("status") in ACTIVE_BATCH_STATUSES]
    batch_terminal = [batch for batch in batches if batch.get("status") in TERMINAL_BATCH_STATUSES]

    for item in task_active + task_terminal + batch_active + batch_terminal:
        summary[_summary_bucket(item["status"])] += 1

    task_active.sort(key=lambda item: _parse_iso(item.get("updated_at")), reverse=True)
    task_terminal.sort(key=lambda item: _parse_iso(item.get("updated_at")), reverse=True)
    batch_active.sort(key=lambda item: _parse_iso(item.get("updated_at")), reverse=True)
    batch_terminal.sort(key=lambda item: _parse_iso(item.get("updated_at")), reverse=True)

    return {
        "summary": summary,
        "tasks": {
            "active": task_active,
            "recent_terminal": task_terminal[:RECENT_TERMINAL_LIMIT],
        },
        "batches": {
            "active": batch_active,
            "recent_terminal": batch_terminal[:RECENT_TERMINAL_LIMIT],
        },
    }
