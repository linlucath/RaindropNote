import logging

from app.enmus.exception import NoteErrorEnum
from app.exceptions.note import NoteError
from app.services.constant import SUPPORT_PLATFORM_MAP

logger = logging.getLogger(__name__)


def build_downloader(
    platform: str,
    *,
    platform_map: dict | None = None,
    log: logging.Logger = logger,
):
    downloaders = SUPPORT_PLATFORM_MAP if platform_map is None else platform_map
    downloader = downloaders.get(platform)
    if downloader is None:
        log.error(f"不支持的平台：{platform}")
        raise NoteError(
            code=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.code,
            message=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.message,
        )

    log.info(f"使用下载器：{downloader.__class__}")
    return downloader
