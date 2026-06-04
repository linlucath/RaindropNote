import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from app.enmus.task_status_enums import TaskStatus
from app.services.task_runtime import TERMINAL_TASK_STATUSES


def _status_file_path(task_id: str, output_dir: Path) -> Path:
    return Path(output_dir) / f'{task_id}.status.json'


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_status(status: Union[str, TaskStatus]) -> str:
    return status.value if isinstance(status, TaskStatus) else status


def read_task_status(task_id: str, output_dir: Path) -> dict:
    status_file = _status_file_path(task_id, output_dir)
    if not status_file.exists():
        return {}

    try:
        with status_file.open('r', encoding='utf-8') as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def write_task_status(
    task_id: str,
    output_dir: Path,
    status: Union[str, TaskStatus],
    message: Optional[str] = None,
    title: Optional[str] = None,
    platform: Optional[str] = None,
) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    existing_payload = read_task_status(task_id=task_id, output_dir=output_dir)
    now = _now_iso()
    payload = {
        'status': _normalize_status(status),
        'message': message if message is not None else existing_payload.get('message', ''),
        'updated_at': now,
        'created_at': existing_payload.get('created_at', now),
        'title': title if title is not None else existing_payload.get('title'),
        'platform': platform if platform is not None else existing_payload.get('platform'),
    }

    status_file = _status_file_path(task_id, output_dir)
    temp_file = status_file.with_suffix('.json.tmp')
    with temp_file.open('w', encoding='utf-8') as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    temp_file.replace(status_file)
    return payload


def request_task_cancel(task_id: str, output_dir: Path) -> dict:
    existing_payload = read_task_status(task_id=task_id, output_dir=output_dir)
    if not existing_payload:
        return {}

    if is_terminal_task_status(existing_payload.get('status')):
        return existing_payload

    return write_task_status(
        task_id=task_id,
        output_dir=output_dir,
        status=TaskStatus.CANCELLING,
        message=existing_payload.get('message', ''),
        title=existing_payload.get('title'),
        platform=existing_payload.get('platform'),
    )


def is_task_cancel_requested(task_id: str, output_dir: Path) -> bool:
    return read_task_status(task_id=task_id, output_dir=output_dir).get('status') == TaskStatus.CANCELLING.value


def cancel_task(
    task_id: str,
    output_dir: Path,
    message: str = '任务已取消',
) -> dict:
    existing_payload = read_task_status(task_id=task_id, output_dir=output_dir)
    if not existing_payload:
        return {}

    if existing_payload.get('status') == TaskStatus.CANCELLED.value:
        return existing_payload

    return write_task_status(
        task_id=task_id,
        output_dir=output_dir,
        status=TaskStatus.CANCELLED,
        message=message,
        title=existing_payload.get('title'),
        platform=existing_payload.get('platform'),
    )


def is_terminal_task_status(status: Union[str, TaskStatus, None]) -> bool:
    if status is None:
        return False
    return _normalize_status(status) in TERMINAL_TASK_STATUSES
