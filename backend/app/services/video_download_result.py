from pathlib import Path
from typing import Any

from pydantic import HttpUrl

from app.models.audio_model import AudioDownloadResult
from app.models.notes_model import NoteResult
from app.utils.url_parser import extract_video_id


def build_video_download_audio_meta(
    *,
    video_url: str | HttpUrl,
    platform: str,
    video_path: Path,
) -> AudioDownloadResult:
    video_url_str = str(video_url)
    video_id = extract_video_id(video_url_str, platform) or video_path.stem
    return AudioDownloadResult(
        file_path="",
        title=video_path.stem,
        duration=0,
        cover_url=None,
        platform=platform,
        video_id=video_id,
        raw_info={"webpage_url": video_url_str},
        video_path=str(video_path),
    )


def build_video_download_payload(*, video_path: Path, resolution: str) -> dict[str, Any]:
    return {
        "file_path": str(video_path),
        "resolution": resolution,
        "filename": video_path.name,
    }


def build_video_download_result(
    *,
    audio_meta: AudioDownloadResult,
    video_path: Path,
    resolution: str,
) -> NoteResult:
    markdown = f"# 视频下载完成\n\n文件：`{video_path}`"
    return NoteResult(
        markdown=markdown,
        transcript=None,
        audio_meta=audio_meta,
        video_download=build_video_download_payload(
            video_path=video_path,
            resolution=resolution,
        ),
    )
