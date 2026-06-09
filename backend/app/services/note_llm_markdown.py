import logging
from pathlib import Path
from typing import Optional

from app.gpt.base import GPT
from app.models.audio_model import AudioDownloadResult
from app.models.gpt_model import GPTSource
from app.models.transcriber_model import TranscriptResult
from app.services import note_generation_plan
from app.services import transcript_markdown

logger = logging.getLogger(__name__)


def build_polish_transcript_source(
    *,
    audio_meta: AudioDownloadResult,
    transcript: TranscriptResult,
    markdown_cache_file: Path,
) -> GPTSource:
    return GPTSource(
        title=audio_meta.title,
        segment=transcript.segments,
        tags=audio_meta.raw_info.get("tags", []),
        language=transcript.language,
        checkpoint_key=markdown_cache_file.stem,
    )


def polish_transcript_markdown(
    *,
    audio_meta: AudioDownloadResult,
    transcript: TranscriptResult,
    gpt: GPT,
    markdown_cache_file: Path,
) -> str:
    source = build_polish_transcript_source(
        audio_meta=audio_meta,
        transcript=transcript,
        markdown_cache_file=markdown_cache_file,
    )
    polished_text = gpt.polish_transcript(source).strip()
    title = transcript_markdown.normalize_transcript_text(audio_meta.title or "未命名视频")
    markdown = "\n\n".join([
        f"# {title}",
        polished_text,
    ]).strip()
    note_generation_plan.write_markdown_cache(markdown_cache_file, markdown)
    logger.info(f"GPT 校对文字稿并缓存成功 ({markdown_cache_file})")
    return markdown


def build_summarize_source(
    *,
    audio_meta: AudioDownloadResult,
    transcript: TranscriptResult,
    markdown_cache_file: Path,
    link: bool,
    screenshot: bool,
    formats: list[str],
    style: Optional[str],
    extras: Optional[str],
    video_img_urls: list[str],
) -> GPTSource:
    return GPTSource(
        title=audio_meta.title,
        segment=transcript.segments,
        tags=audio_meta.raw_info.get("tags", []),
        screenshot=screenshot,
        video_img_urls=video_img_urls,
        link=link,
        _format=formats,
        style=style,
        extras=extras,
        checkpoint_key=markdown_cache_file.stem,
    )


def summarize_note_markdown(
    *,
    audio_meta: AudioDownloadResult,
    transcript: TranscriptResult,
    gpt: GPT,
    markdown_cache_file: Path,
    link: bool,
    screenshot: bool,
    formats: list[str],
    style: Optional[str],
    extras: Optional[str],
    video_img_urls: list[str],
) -> str:
    source = build_summarize_source(
        audio_meta=audio_meta,
        transcript=transcript,
        markdown_cache_file=markdown_cache_file,
        link=link,
        screenshot=screenshot,
        formats=formats,
        style=style,
        extras=extras,
        video_img_urls=video_img_urls,
    )
    markdown = gpt.summarize(source)
    note_generation_plan.write_markdown_cache(markdown_cache_file, markdown)
    logger.info(f"GPT 总结并缓存成功 ({markdown_cache_file})")
    return markdown
