import re
from typing import Optional

from app.models.transcriber_model import TranscriptResult, TranscriptSegment


def _build_transcript_result(
    language: str,
    segments: list[TranscriptSegment],
    raw: dict,
) -> Optional[TranscriptResult]:
    if not segments:
        return None

    return TranscriptResult(
        language=language,
        full_text=' '.join(segment.text for segment in segments),
        segments=segments,
        raw=raw,
    )


def _srt_time_to_seconds(value: str) -> float:
    hours, minutes, seconds = value.replace(',', '.').split(':')
    return float(hours) * 3600 + float(minutes) * 60 + float(seconds)


def parse_srt_transcript(srt_content: str, language: str) -> Optional[TranscriptResult]:
    normalized_content = srt_content.replace('\r\n', '\n').replace('\r', '\n')
    pattern = (
        r'(\d+)\n'
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*'
        r'(\d{2}:\d{2}:\d{2},\d{3})\n'
        r'(.*?)(?=\n\n|\n\d+\n|$)'
    )
    segments = []

    for _, start_time, end_time, text in re.findall(pattern, normalized_content, re.DOTALL):
        text = text.strip()
        if not text:
            continue

        segments.append(
            TranscriptSegment(
                start=_srt_time_to_seconds(start_time),
                end=_srt_time_to_seconds(end_time),
                text=text,
            )
        )

    return _build_transcript_result(
        language=language,
        segments=segments,
        raw={'source': 'bilibili_subtitle', 'format': 'srt'},
    )


def parse_bilibili_json_transcript(
    subtitle_data: dict,
    language: str,
    raw: Optional[dict] = None,
) -> Optional[TranscriptResult]:
    segments = []

    for event in subtitle_data.get('events', []):
        start_ms = event.get('tStartMs', 0)
        duration_ms = event.get('dDurationMs', 0)
        segs = event.get('segs', [])
        text = ''.join(segment.get('utf8', '') for segment in segs).strip()

        if not text:
            continue

        segments.append(
            TranscriptSegment(
                start=start_ms / 1000.0,
                end=(start_ms + duration_ms) / 1000.0,
                text=text,
            )
        )

    return _build_transcript_result(
        language=language,
        segments=segments,
        raw=raw or {'source': 'bilibili_subtitle', 'format': 'json3'},
    )
