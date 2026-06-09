import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.models.audio_model import AudioDownloadResult


@dataclass(frozen=True)
class NoteCachePaths:
    audio_cache_file: Path
    transcript_cache_file: Path
    markdown_cache_file: Path


@dataclass(frozen=True)
class GenerationModeBranch:
    mode: str | None
    is_transcript_only: bool
    is_polished_transcript: bool


@dataclass(frozen=True)
class MediaSourcePlan:
    need_full_download: bool
    use_subtitle_only_audio_meta: bool
    skip_download: bool


def build_cache_paths(output_dir: Path | str, task_id: str | None) -> NoteCachePaths:
    task_key = str(task_id)
    note_output_dir = Path(output_dir)
    return NoteCachePaths(
        audio_cache_file=note_output_dir / f"{task_key}_audio.json",
        transcript_cache_file=note_output_dir / f"{task_key}_transcript.json",
        markdown_cache_file=note_output_dir / f"{task_key}_markdown.md",
    )


def prepare_mode_branch(mode: str | None) -> GenerationModeBranch:
    return GenerationModeBranch(
        mode=mode,
        is_transcript_only=mode == "transcript",
        is_polished_transcript=mode == "polished_transcript",
    )


def prepare_media_source(
    *,
    platform: str,
    screenshot: bool,
    video_understanding: bool,
) -> MediaSourcePlan:
    need_full_download = screenshot or video_understanding
    return MediaSourcePlan(
        need_full_download=need_full_download,
        use_subtitle_only_audio_meta=platform == "youtube" and not need_full_download,
        skip_download=not need_full_download,
    )


def write_audio_cache(audio_cache_file: Path, audio_meta: AudioDownloadResult) -> None:
    audio_cache_file.parent.mkdir(parents=True, exist_ok=True)
    audio_cache_file.write_text(
        json.dumps(asdict(audio_meta), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_markdown_cache(markdown_cache_file: Path, markdown: str) -> None:
    markdown_cache_file.parent.mkdir(parents=True, exist_ok=True)
    markdown_cache_file.write_text(markdown, encoding="utf-8")
