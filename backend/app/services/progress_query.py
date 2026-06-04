import os
from pathlib import Path

from app.services.progress_files import (
    ACTIVE_BATCH_STATUSES,
    ACTIVE_TASK_STATUSES,
    TERMINAL_BATCH_STATUSES,
    TERMINAL_TASK_STATUSES,
    build_overview,
    build_task_item,
    infer_task_platform,
    infer_task_title,
    load_batch_items,
    load_task_items,
    normalize_stale_cancelling_task,
    parse_iso,
    result_file_for_task,
    safe_read_json,
    summary_bucket,
)
from app.services.progress_state import write_task_status
from app.services.task_runtime import (
    default_batch_output_dir,
    default_note_output_dir,
)


NOTE_OUTPUT_DIR = default_note_output_dir()
BATCH_OUTPUT_DIR = default_batch_output_dir(NOTE_OUTPUT_DIR)
CANCELLING_STALE_AFTER_SECONDS = int(os.getenv("TASK_CANCELLING_STALE_AFTER_SECONDS", "3600"))
RECENT_TERMINAL_LIMIT = 20


def _note_output_dir() -> Path:
    return Path(NOTE_OUTPUT_DIR)


def _batch_output_dir() -> Path:
    return Path(BATCH_OUTPUT_DIR)


def _safe_read_json(path: Path) -> dict | None:
    return safe_read_json(path)


def _parse_iso(value: str | None):
    return parse_iso(value)


def _result_file_for_task(task_id: str) -> Path:
    return result_file_for_task(_note_output_dir(), task_id)


def _infer_task_title(status_payload: dict, result_payload: dict | None) -> str:
    return infer_task_title(status_payload, result_payload)


def _infer_task_platform(status_payload: dict, result_payload: dict | None) -> str:
    return infer_task_platform(status_payload, result_payload)


def _build_task_item(task_id: str, status_payload: dict, result_payload: dict | None) -> dict:
    return build_task_item(task_id, status_payload, result_payload)


def _normalize_stale_cancelling_task(task_id: str, status_payload: dict) -> dict:
    return normalize_stale_cancelling_task(
        task_id,
        status_payload,
        note_output_dir=_note_output_dir(),
        stale_cancelling_after_seconds=CANCELLING_STALE_AFTER_SECONDS,
        write_status=write_task_status,
    )


def _load_tasks() -> list[dict]:
    return load_task_items(
        _note_output_dir(),
        stale_cancelling_after_seconds=CANCELLING_STALE_AFTER_SECONDS,
        write_status=write_task_status,
    )


def _load_batches() -> list[dict]:
    return load_batch_items(_batch_output_dir())


def _summary_bucket(status: str) -> str:
    return summary_bucket(status)


def build_progress_overview() -> dict:
    return build_overview(
        note_output_dir=_note_output_dir(),
        batch_output_dir=_batch_output_dir(),
        stale_cancelling_after_seconds=CANCELLING_STALE_AFTER_SECONDS,
        write_status=write_task_status,
        recent_terminal_limit=RECENT_TERMINAL_LIMIT,
    )
