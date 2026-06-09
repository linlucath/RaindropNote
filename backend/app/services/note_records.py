import logging
from typing import Callable, Optional

DeleteTaskByTaskId = Callable[[str], int]
DeleteTaskByVideo = Callable[[str, str], int]
InsertVideoTask = Callable[..., object]

# Compatibility patch hooks. The DAO import stays lazy so importing note services
# does not initialize the database engine.
delete_task_by_task_id: DeleteTaskByTaskId | None = None
delete_task_by_video: DeleteTaskByVideo | None = None
insert_video_task: InsertVideoTask | None = None


def _delete_task_by_task_id(task_id: str) -> int:
    if delete_task_by_task_id is not None:
        return delete_task_by_task_id(task_id)

    from app.db.video_task_dao import delete_task_by_task_id as delete_task

    return delete_task(task_id)


def _delete_task_by_video(video_id: str, platform: str) -> int:
    if delete_task_by_video is not None:
        return delete_task_by_video(video_id, platform)

    from app.db.video_task_dao import delete_task_by_video as delete_task

    return delete_task(video_id, platform)


def _insert_video_task(*, video_id: str, platform: str, task_id: str) -> object:
    if insert_video_task is not None:
        return insert_video_task(video_id=video_id, platform=platform, task_id=task_id)

    from app.db.video_task_dao import insert_video_task as insert_task

    return insert_task(video_id=video_id, platform=platform, task_id=task_id)


def delete_note_record(
    *,
    video_id: Optional[str] = None,
    platform: Optional[str] = None,
    task_id: Optional[str] = None,
    log: logging.Logger,
) -> int:
    if task_id:
        log.info(f"删除笔记记录 (task_id={task_id})")
        return _delete_task_by_task_id(task_id)

    if not video_id or not platform:
        log.warning("删除笔记记录失败：缺少 task_id，且未提供完整的 video_id/platform")
        return 0

    log.info(f"删除笔记记录 (video_id={video_id}, platform={platform})")
    return _delete_task_by_video(video_id, platform)


def save_note_record(
    *,
    video_id: str,
    platform: str,
    task_id: str,
    log: logging.Logger,
) -> None:
    try:
        _insert_video_task(video_id=video_id, platform=platform, task_id=task_id)
        log.info(f"已保存任务记录到数据库 (video_id={video_id}, platform={platform}, task_id={task_id})")
    except Exception as exc:
        log.error(f"保存任务记录失败：{exc}")
