import logging
from typing import Callable, Optional, Union

from pydantic import HttpUrl

from app.enmus.task_status_enums import TaskStatus
from app.models.audio_model import AudioDownloadResult
from app.models.notes_model import NoteResult
from app.models.transcriber_model import TranscriptResult
from app.services import note_result_payload

UpdateStatus = Callable[..., None]
SaveMetadata = Callable[..., None]


def complete_note_generation(
    *,
    task_id: Optional[str],
    markdown: str,
    video_url: Union[str, HttpUrl],
    transcript: TranscriptResult,
    audio_meta: AudioDownloadResult,
    platform: str,
    success_message: str,
    update_status: UpdateStatus,
    save_metadata: SaveMetadata,
    log: logging.Logger,
) -> NoteResult:
    update_status(task_id, TaskStatus.SAVING, title=audio_meta.title, platform=platform)
    save_metadata(video_id=audio_meta.video_id, platform=platform, task_id=task_id)
    update_status(task_id, TaskStatus.SUCCESS, title=audio_meta.title, platform=platform)
    log.info(f"{success_message} (task_id={task_id})")
    return note_result_payload.build_note_result(
        markdown=markdown,
        video_url=video_url,
        transcript=transcript,
        audio_meta=audio_meta,
    )
