import logging
from pathlib import Path
from typing import Optional, Union

from app.enmus.task_status_enums import TaskStatus
from app.services import note_result_payload
from app.services.progress_state import cancel_task, is_task_cancel_requested, write_task_status


class TaskCancelledError(RuntimeError):
    pass


def update_task_status(
    *,
    task_id: Optional[str],
    output_dir: Path,
    status: Union[str, TaskStatus],
    message: Optional[str] = None,
    title: Optional[str] = None,
    platform: Optional[str] = None,
    log: logging.Logger,
) -> None:
    if not task_id:
        return

    try:
        payload = build_status_payload(
            task_id=task_id,
            status=status,
            message=message,
            title=title,
            platform=platform,
        )
        write_task_status(
            task_id=payload["task_id"],
            output_dir=output_dir,
            status=payload["status"],
            message=payload["message"],
            title=payload["title"],
            platform=payload["platform"],
        )
    except Exception as exc:
        log.error(f"写入状态文件失败 (task_id={task_id})：{exc}")


def build_status_payload(
    *,
    task_id: str,
    status: Union[str, TaskStatus],
    message: Optional[str] = None,
    title: Optional[str] = None,
    platform: Optional[str] = None,
) -> dict:
    return note_result_payload.build_status_payload(
        task_id=task_id,
        status=status,
        message=message,
        title=title,
        platform=platform,
    )


def cancel_if_requested(*, task_id: Optional[str], output_dir: Path) -> None:
    if not task_id:
        return

    if not is_task_cancel_requested(task_id=task_id, output_dir=output_dir):
        return

    cancel_task(task_id=task_id, output_dir=output_dir)
    raise TaskCancelledError("任务已取消")


def handle_task_exception(*, task_id: str, exc: Exception, update_status, log: logging.Logger) -> None:
    log.error(f"任务异常 (task_id={task_id})", exc_info=True)
    update_status(task_id, TaskStatus.FAILED, message=format_exception_message(exc))


def format_exception_message(exc: Exception) -> str:
    return note_result_payload.format_exception_message(exc)
