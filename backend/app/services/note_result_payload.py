import json
from typing import Optional, Union

from pydantic import HttpUrl

from app.enmus.task_status_enums import TaskStatus
from app.models.audio_model import AudioDownloadResult
from app.models.notes_model import NoteResult
from app.models.transcriber_model import TranscriptResult
from app.utils.note_helper import prepend_source_link


def normalize_status(status: Union[str, TaskStatus]) -> str:
    return status.value if isinstance(status, TaskStatus) else status


def build_status_payload(
    task_id: str,
    status: Union[str, TaskStatus],
    message: Optional[str] = None,
    title: Optional[str] = None,
    platform: Optional[str] = None,
) -> dict:
    return {
        "task_id": task_id,
        "status": normalize_status(status),
        "message": message,
        "title": title,
        "platform": platform,
    }


def format_exception_message(exc: Exception) -> str:
    error_message = getattr(exc, "detail", str(exc))
    if isinstance(error_message, dict):
        try:
            return json.dumps(error_message, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(error_message)
    return str(error_message)


def build_note_result(
    markdown: str,
    video_url: Union[str, HttpUrl],
    transcript: TranscriptResult,
    audio_meta: AudioDownloadResult,
) -> NoteResult:
    return NoteResult(
        markdown=prepend_source_link(markdown, str(video_url)),
        transcript=transcript,
        audio_meta=audio_meta,
    )
