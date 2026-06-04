import json
import logging
from pathlib import Path
from typing import Optional

from app.models.transcriber_model import TranscriptResult, TranscriptSegment

logger = logging.getLogger(__name__)

SUBTITLE_TRANSCRIPT_SOURCES = {"bilibili_subtitle", "youtube_transcript_api"}


def is_subtitle_transcript_data(data: dict) -> bool:
    raw = (data or {}).get("raw") or {}
    return isinstance(raw, dict) and raw.get("source") in SUBTITLE_TRANSCRIPT_SOURCES


def is_subtitle_transcript_result(transcript: TranscriptResult) -> bool:
    raw = transcript.raw or {}
    return isinstance(raw, dict) and raw.get("source") in SUBTITLE_TRANSCRIPT_SOURCES


def load_subtitle_transcript_cache(
    transcript_cache_file: Path,
    *,
    log=logger,
) -> Optional[TranscriptResult]:
    data = json.loads(transcript_cache_file.read_text(encoding="utf-8"))
    if not is_subtitle_transcript_data(data):
        log.info(f"转写缓存不是平台字幕来源，忽略旧缓存 ({transcript_cache_file})")
        return None

    segments = [TranscriptSegment(**seg) for seg in data.get("segments", [])]
    return TranscriptResult(
        language=data.get("language"),
        full_text=data["full_text"],
        segments=segments,
        raw=data.get("raw"),
    )
