from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException

from app.enmus.exception import NoteErrorEnum
from app.exceptions.note import NoteError
from app.services import note_tasks
from app.services.constant import SUPPORT_PLATFORM_MAP
from app.utils.url_parser import infer_platform_from_url
from app.validators.video_url_validator import is_supported_video_url


def normalize_generation_mode(mode: Optional[str]) -> str:
    try:
        return note_tasks.normalize_generation_mode(mode)
    except note_tasks.NoteTaskValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def validate_supported_url(value):
    url = str(value)
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https") and not is_supported_video_url(url):
        raise NoteError(
            code=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.code,
            message=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.message,
        )

    return value


def reject_unsupported_platform() -> None:
    raise HTTPException(
        status_code=400,
        detail=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.message,
    )


def resolve_request_platform(*, video_url: str, platform: Optional[str]) -> str:
    parsed = urlparse(str(video_url))
    if parsed.scheme not in ("http", "https"):
        reject_unsupported_platform()

    requested_platform = (platform or "").strip()
    if requested_platform and requested_platform in SUPPORT_PLATFORM_MAP:
        return requested_platform
    if requested_platform:
        reject_unsupported_platform()

    inferred_platform = infer_platform_from_url(video_url)
    if inferred_platform:
        return inferred_platform

    raise HTTPException(status_code=400, detail="请选择平台")
