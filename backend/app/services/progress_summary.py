from datetime import datetime, timezone
from typing import Optional

from app.enmus.task_status_enums import TaskStatus


SUMMARY_BUCKETS = ("pending", "running", "cancelling", "success", "failed", "cancelled")


def parse_iso(value: Optional[str]) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def summary_bucket(status: str) -> str:
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


def build_summary(items: list[dict]) -> dict:
    summary = {bucket: 0 for bucket in SUMMARY_BUCKETS}
    for item in items:
        status = item.get("status")
        if status is None:
            continue
        summary[summary_bucket(status)] += 1
    return summary


def group_items_by_status(
    items: list[dict],
    *,
    active_statuses: set[str],
    terminal_statuses: set[str],
) -> tuple[list[dict], list[dict]]:
    active = [item for item in items if item.get("status") in active_statuses]
    terminal = [item for item in items if item.get("status") in terminal_statuses]

    active.sort(key=lambda item: parse_iso(item.get("updated_at")), reverse=True)
    terminal.sort(key=lambda item: parse_iso(item.get("updated_at")), reverse=True)
    return active, terminal
