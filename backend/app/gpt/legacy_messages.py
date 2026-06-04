from __future__ import annotations

from datetime import timedelta
from typing import List

from app.gpt.prompt import AI_SUM, BASE_PROMPT, LINK, SCREENSHOT
from app.models.transcriber_model import TranscriptSegment


def format_time(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))[2:]


def build_segment_text(segments: List[TranscriptSegment]) -> str:
    return "\n".join(
        f"{format_time(segment.start)} - {segment.text.strip()}"
        for segment in segments
    )


def ensure_segments_type(segments) -> List[TranscriptSegment]:
    return [
        TranscriptSegment(**segment) if isinstance(segment, dict) else segment
        for segment in segments
    ]


def build_legacy_prompt_messages(
    segments: List[TranscriptSegment],
    *,
    title: str,
    tags: str,
    include_screenshot: bool = False,
    include_link: bool = False,
) -> list[dict[str, str]]:
    content = BASE_PROMPT.format(
        video_title=title,
        segment_text=build_segment_text(segments),
        tags=tags,
    )
    if include_screenshot:
        content += SCREENSHOT
    if include_link:
        content += LINK
    return [{"role": "user", "content": content + AI_SUM}]
