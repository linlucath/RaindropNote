import logging
from typing import Callable, Union

import requests
from pydantic import HttpUrl

from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult
from app.services import subtitle_transcripts
from app.utils.url_parser import extract_video_id

logger = logging.getLogger(__name__)

SUBTITLE_TRANSCRIPT_SOURCES = subtitle_transcripts.SUBTITLE_TRANSCRIPT_SOURCES


def is_subtitle_transcript_data(data: dict) -> bool:
    return subtitle_transcripts.is_subtitle_transcript_data(data)


def is_subtitle_transcript_result(transcript: TranscriptResult) -> bool:
    return subtitle_transcripts.is_subtitle_transcript_result(transcript)


def fetch_video_title(
    video_url: str,
    platform: str,
    *,
    requests_get: Callable = requests.get,
    log=logger,
) -> str | None:
    if platform != "youtube":
        return None

    endpoint = "https://www.youtube.com/oembed"
    try:
        response = requests_get(
            endpoint,
            params={"url": video_url, "format": "json"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        title = (data.get("title") or "").strip()
        return title or None
    except Exception as exc:
        log.warning(f"获取 YouTube 标题失败，将回退到 video_id: {exc}")
        return None


def build_subtitle_only_audio_meta(
    *,
    video_url: Union[str, HttpUrl],
    platform: str,
    transcript: TranscriptResult,
    title_lookup: Callable[[str, str], str | None] = fetch_video_title,
) -> AudioDownloadResult:
    video_url_str = str(video_url)
    video_id = extract_video_id(video_url_str, platform) or video_url_str
    raw = transcript.raw or {}
    duration = 0.0
    if transcript.segments:
        duration = max(float(segment.end or 0) for segment in transcript.segments)

    title = (
        raw.get("title")
        or raw.get("video_title")
        or title_lookup(video_url_str, platform)
        or video_id
    )
    return AudioDownloadResult(
        file_path="",
        title=title,
        duration=duration,
        cover_url=raw.get("thumbnail") or raw.get("cover_url"),
        platform=platform,
        video_id=video_id,
        raw_info={
            "tags": raw.get("tags", []),
            "webpage_url": video_url_str,
            "subtitle_source": raw.get("source"),
        },
        video_path=None,
    )
