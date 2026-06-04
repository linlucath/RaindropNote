import logging
from pathlib import Path
from typing import Any, Callable, Optional

from app.models.audio_model import AudioDownloadResult
from app.utils.note_helper import replace_content_markers
from app.utils.screenshot_marker import extract_screenshot_timestamps
from app.utils.video_helper import generate_screenshot as default_generate_screenshot

logger = logging.getLogger(__name__)


def insert_screenshots(
    markdown: str,
    video_path: Path,
    *,
    image_output_dir: str,
    image_base_url: str,
    generate_screenshot: Callable[[str, str, int, int], str] | None = None,
    log: Any = logger,
) -> str | None:
    generate_screenshot = generate_screenshot or default_generate_screenshot
    matches = extract_screenshot_timestamps(markdown)
    for idx, (marker, ts) in enumerate(matches):
        try:
            img_path = generate_screenshot(str(video_path), str(image_output_dir), ts, idx)
            filename = Path(img_path).name
            img_url = f"{image_base_url.rstrip('/')}/{filename}"
            markdown = markdown.replace(marker, f"![]({img_url})", 1)
        except Exception as exc:
            log.error(f"生成截图失败 (timestamp={ts})：{exc}")
            return None
    return markdown


def post_process_markdown(
    *,
    markdown: str,
    video_path: Optional[Path],
    formats: list[str],
    audio_meta: AudioDownloadResult,
    platform: str,
    insert_screenshots: Callable[[str, Path], str | None] | None = None,
    replace_markers: Callable[[str, str, str], str] = replace_content_markers,
    log: Any = logger,
) -> str | None:
    if "screenshot" in formats and video_path:
        try:
            if insert_screenshots is None:
                raise ValueError("insert_screenshots callback is required")
            markdown = insert_screenshots(markdown, video_path)
        except Exception:
            log.warning("截图插入失败，跳过该步骤")

    if "link" in formats:
        try:
            markdown = replace_markers(markdown, video_id=audio_meta.video_id, platform=platform)
        except Exception as exc:
            log.warning(f"链接插入失败，跳过该步骤：{exc}")

    return markdown
