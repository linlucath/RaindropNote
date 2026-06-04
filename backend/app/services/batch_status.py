from typing import Optional

from app.enmus.task_status_enums import TaskStatus
from app.services.task_runtime import COMPLETED_ITEM_STATUSES, TERMINAL_BATCH_STATUSES

SUCCESSFUL_ITEM_STATUSES = {TaskStatus.SUCCESS.value, "SKIPPED"}


def is_batch_terminal(status: Optional[str]) -> bool:
    return status in TERMINAL_BATCH_STATUSES


def count_updates(batch: dict) -> dict[str, int]:
    items = batch["items"]
    completed = sum(1 for item in items if item["status"] in COMPLETED_ITEM_STATUSES)
    return {
        "completed": completed,
        "total": len(items),
    }


def next_status(batch: dict, *, finalize_success: bool = True) -> Optional[str]:
    if batch["completed"] != batch["total"]:
        return None
    if batch.get("cancel_requested"):
        return TaskStatus.CANCELLED.value
    if not finalize_success or is_batch_terminal(batch.get("status")):
        return None
    if all(item["status"] in SUCCESSFUL_ITEM_STATUSES for item in batch["items"]):
        return TaskStatus.SUCCESS.value
    return TaskStatus.FAILED.value
