import json
import os
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Optional

from app.downloaders.bilibili_subtitle_parser import (
    parse_bilibili_json_transcript,
    parse_srt_transcript,
)
from app.models.transcriber_model import TranscriptResult


@dataclass(frozen=True)
class BilibiliSubtitleSelection:
    language: str
    info: Mapping[str, Any]


def choose_bilibili_subtitle(
    subtitles: Mapping[str, Mapping[str, Any]],
    preferred_langs: Sequence[str],
) -> Optional[BilibiliSubtitleSelection]:
    for language in preferred_langs:
        subtitle_info = subtitles.get(language)
        if subtitle_info:
            return BilibiliSubtitleSelection(language=language, info=subtitle_info)

    for language, subtitle_info in subtitles.items():
        if language != 'danmaku':
            return BilibiliSubtitleSelection(language=language, info=subtitle_info)

    return None


def build_bilibili_subtitle_file(
    output_dir: str,
    video_id: str,
    language: str,
    subtitle_info: Mapping[str, Any],
) -> str:
    ext = subtitle_info.get('ext', 'srt')
    return os.path.join(output_dir, f'{video_id}.{language}.{ext}')


def parse_bilibili_srt_content(
    srt_content: str,
    language: str,
    *,
    request_logger: logging.Logger,
) -> Optional[TranscriptResult]:
    try:
        result = parse_srt_transcript(srt_content, language)
        if result:
            request_logger.info('成功解析B站SRT字幕，共 %s 段', len(result.segments))
        return result
    except Exception as exc:
        request_logger.warning('解析SRT字幕失败: %s', exc)
        return None


def parse_bilibili_json3_subtitle_file(
    subtitle_file: str,
    language: str,
    *,
    request_logger: logging.Logger,
) -> Optional[TranscriptResult]:
    try:
        with open(subtitle_file, 'r', encoding='utf-8') as file:
            data = json.load(file)

        result = parse_bilibili_json_transcript(
            data,
            language,
            raw={'source': 'bilibili_subtitle', 'file': subtitle_file},
        )
        if result:
            request_logger.info('成功解析B站字幕，共 %s 段', len(result.segments))
        return result
    except Exception as exc:
        request_logger.warning('解析字幕文件失败: %s', exc)
        return None
