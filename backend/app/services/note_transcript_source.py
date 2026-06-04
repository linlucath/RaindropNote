import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.models.transcriber_model import TranscriptResult
from app.services import subtitle_transcripts

logger = logging.getLogger(__name__)


def load_or_download_platform_transcript(
    *,
    transcript_cache_file: Path,
    downloader: Any,
    video_url: str,
    log=logger,
) -> TranscriptResult | None:
    if transcript_cache_file.exists():
        log.info(f"检测到转写缓存 ({transcript_cache_file})，尝试读取")
        try:
            transcript = subtitle_transcripts.load_subtitle_transcript_cache(
                transcript_cache_file,
                log=log,
            )
            if transcript:
                log.info(f"已从缓存加载转写结果，共 {len(transcript.segments)} 段")
                return transcript
        except Exception as exc:
            log.warning(f"加载转写缓存失败: {exc}")

    log.info("尝试获取平台字幕（优先于音频下载）...")
    try:
        transcript = downloader.download_subtitles(video_url)
        if transcript and transcript.segments:
            log.info(f"成功获取平台字幕，共 {len(transcript.segments)} 段")
            transcript_cache_file.parent.mkdir(parents=True, exist_ok=True)
            transcript_cache_file.write_text(
                json.dumps(asdict(transcript), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return transcript

        log.info("平台无可用字幕")
        return None
    except Exception as exc:
        log.warning(f"获取平台字幕失败: {exc}")
        return None
