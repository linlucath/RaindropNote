import logging
from typing import Optional

from app.db.video_task_dao import delete_task_by_task_id, delete_task_by_video, insert_video_task


def delete_note_record(
    *,
    video_id: Optional[str] = None,
    platform: Optional[str] = None,
    task_id: Optional[str] = None,
    log: logging.Logger,
) -> int:
    if task_id:
        log.info(f"删除笔记记录 (task_id={task_id})")
        return delete_task_by_task_id(task_id)

    if not video_id or not platform:
        log.warning("删除笔记记录失败：缺少 task_id，且未提供完整的 video_id/platform")
        return 0

    log.info(f"删除笔记记录 (video_id={video_id}, platform={platform})")
    return delete_task_by_video(video_id, platform)


def save_note_record(
    *,
    video_id: str,
    platform: str,
    task_id: str,
    log: logging.Logger,
) -> None:
    try:
        insert_video_task(video_id=video_id, platform=platform, task_id=task_id)
        log.info(f"已保存任务记录到数据库 (video_id={video_id}, platform={platform}, task_id={task_id})")
    except Exception as exc:
        log.error(f"保存任务记录失败：{exc}")
