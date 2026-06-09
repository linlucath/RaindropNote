import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Optional

from app.enmus.task_status_enums import TaskStatus
from app.services.batch_preview import infer_platform_from_url
from app.services import batch_status
from app.services.task_runtime import (
    COMPLETED_ITEM_STATUSES,
    TERMINAL_BATCH_STATUSES,
    default_batch_output_dir,
)

BATCH_OUTPUT_DIR = default_batch_output_dir()

_batch_lock = Lock()
_batches: dict[str, dict] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_batch_title(mode: str) -> str:
    return "批量文字稿任务"


def default_source_label(
    videos: list,
    *,
    infer_platform: Callable[[str], str] = infer_platform_from_url,
) -> str:
    if videos:
        platform = getattr(videos[0], "platform", None) or infer_platform(videos[0].video_url)
        if platform == "youtube":
            return "YouTube"
        if platform == "bilibili":
            return "Bilibili"
    return "未知来源"


def create_batch_payload(
    batch_id: str,
    request,
    *,
    infer_platform: Callable[[str], str] = infer_platform_from_url,
) -> dict:
    now = now_iso()
    return {
        "batch_id": batch_id,
        "title": default_batch_title(request.mode),
        "source_label": default_source_label(request.videos, infer_platform=infer_platform),
        "status": "PENDING",
        "created_at": now,
        "updated_at": now,
        "cancel_requested": False,
        "current_item_title": None,
        "current_item_index": None,
        "total": len(request.videos),
        "completed": 0,
        "items": [
            {
                "video_id": video.video_id,
                "video_url": video.video_url,
                "title": video.title,
                "platform": video.platform or infer_platform(video.video_url),
                "status": "PENDING",
                "task_id": None,
                "message": "",
            }
            for video in request.videos
        ],
    }


def is_batch_terminal(status: Optional[str]) -> bool:
    return batch_status.is_batch_terminal(status)


def _resolve_output_dir(output_dir: Path | str | None) -> Path:
    return Path(output_dir) if output_dir is not None else BATCH_OUTPUT_DIR


def _resolve_batches(batches: dict[str, dict] | None) -> dict[str, dict]:
    return batches if batches is not None else _batches


def _resolve_batch_lock(batch_lock: Any = None) -> Any:
    return batch_lock if batch_lock is not None else _batch_lock


def load_batch(
    batch_id: str,
    *,
    output_dir: Path | str | None = None,
    batches: dict[str, dict] | None = None,
) -> Optional[dict]:
    active_batches = _resolve_batches(batches)
    if batch_id in active_batches:
        return active_batches[batch_id]
    batch_output_dir = _resolve_output_dir(output_dir)
    path = batch_output_dir / f"{batch_id}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    active_batches[batch_id] = payload
    return payload


def save_batch(batch: dict, *, output_dir: Path | str | None = None) -> None:
    batch_output_dir = _resolve_output_dir(output_dir)
    batch_output_dir.mkdir(parents=True, exist_ok=True)
    path = batch_output_dir / f"{batch['batch_id']}.json"
    path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")


def _refresh_counts(batch: dict) -> None:
    batch.update(batch_status.count_updates(batch))


def update_batch(
    batch_id: str,
    *,
    output_dir: Path | str | None = None,
    batches: dict[str, dict] | None = None,
    batch_lock: Any = None,
    **updates,
) -> dict:
    active_batches = _resolve_batches(batches)
    with _resolve_batch_lock(batch_lock):
        batch = active_batches[batch_id]
        batch.update(updates)
        batch["updated_at"] = now_iso()
        _refresh_counts(batch)
        next_status = batch_status.next_status(batch)
        if next_status is not None:
            batch["status"] = next_status
        save_batch(batch, output_dir=output_dir)
        return batch


def set_batch_item(
    batch_id: str,
    index: int,
    *,
    output_dir: Path | str | None = None,
    batches: dict[str, dict] | None = None,
    batch_lock: Any = None,
    **updates,
) -> None:
    active_batches = _resolve_batches(batches)
    with _resolve_batch_lock(batch_lock):
        batch = active_batches[batch_id]
        batch["items"][index].update(updates)
        batch["updated_at"] = now_iso()
        _refresh_counts(batch)
        next_status = batch_status.next_status(batch, finalize_success=False)
        if next_status is not None:
            batch["status"] = next_status
        save_batch(batch, output_dir=output_dir)


def is_cancel_requested(
    batch_id: str,
    *,
    batches: dict[str, dict] | None = None,
) -> bool:
    return bool(_resolve_batches(batches)[batch_id].get("cancel_requested"))


def finalize_batch_cancel(
    batch_id: str,
    message: str = "批量任务已取消",
    *,
    output_dir: Path | str | None = None,
    batches: dict[str, dict] | None = None,
    batch_lock: Any = None,
) -> dict:
    active_batches = _resolve_batches(batches)
    with _resolve_batch_lock(batch_lock):
        batch = active_batches[batch_id]
        for item in batch["items"]:
            if item["status"] == "PENDING":
                item["status"] = TaskStatus.CANCELLED.value
                item["message"] = message
        batch["status"] = TaskStatus.CANCELLED.value
        batch["cancel_requested"] = True
        batch["current_item_title"] = None
        batch["current_item_index"] = None
        batch["updated_at"] = now_iso()
        _refresh_counts(batch)
        save_batch(batch, output_dir=output_dir)
        return batch
