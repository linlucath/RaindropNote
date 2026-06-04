import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, List, Optional, Union, Any

from pydantic import HttpUrl

from app.downloaders.base import Downloader
from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.models.audio_model import AudioDownloadResult
from app.utils.video_reader import VideoReader

logger = logging.getLogger(__name__)


@dataclass
class MediaDownloadResult:
    audio_meta: AudioDownloadResult
    video_path: Optional[Path]
    video_img_urls: List[str]


StatusUpdater = Callable[..., None]
ExceptionHandler = Callable[[str, Exception], None]


def download_media(
    downloader: Downloader,
    video_url: Union[str, HttpUrl],
    quality: DownloadQuality,
    audio_cache_file: Path,
    status_phase: TaskStatus,
    platform: str,
    output_path: Optional[str],
    screenshot: bool,
    video_understanding: bool,
    video_interval: int,
    grid_size: List[int],
    update_status: StatusUpdater,
    handle_exception: ExceptionHandler,
    skip_download: bool = False,
    video_reader_cls: Any = VideoReader,
    log: logging.Logger = logger,
) -> MediaDownloadResult:
    """
    Download or load media metadata for note generation.

    Callers provide paths and side-effect callbacks so monkeypatched output
    directories and NoteGenerator-compatible error handling stay at the edge.
    """
    task_id = audio_cache_file.stem.split("_")[0]
    update_status(task_id, status_phase)

    # 已有缓存，尝试加载
    if audio_cache_file.exists():
        log.info(f"检测到音频缓存 ({audio_cache_file})，直接读取")
        try:
            data = json.loads(audio_cache_file.read_text(encoding="utf-8"))
            return MediaDownloadResult(
                audio_meta=AudioDownloadResult(**data),
                video_path=None,
                video_img_urls=[],
            )
        except Exception as exc:
            log.warning(f"读取音频缓存失败，将重新下载：{exc}")

    # 有字幕且不需要截图/视频理解时，只提取元信息不下载文件
    if skip_download:
        log.info("已有字幕，仅提取视频元信息（不下载音视频）")
        try:
            audio = downloader.download(
                video_url=video_url,
                quality=quality,
                output_dir=output_path,
                need_video=False,
                skip_download=True,
            )
            audio_cache_file.write_text(
                json.dumps(asdict(audio), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info(f"元信息提取完成 ({audio_cache_file})")
            return MediaDownloadResult(
                audio_meta=audio,
                video_path=None,
                video_img_urls=[],
            )
        except Exception as exc:
            log.warning(f"元信息提取失败，将尝试完整下载: {exc}")

    # 判断是否需要下载视频
    need_video = screenshot or video_understanding
    if screenshot and not grid_size:
        grid_size = [2, 2]

    video_path = None
    video_img_urls: List[str] = []
    frame_interval = video_interval if video_interval and video_interval > 0 else 6
    if need_video:
        try:
            log.info("开始下载视频")
            video_path_str = downloader.download_video(video_url)
            video_path = Path(video_path_str)
            log.info(f"视频下载完成：{video_path}")

            if grid_size:
                video_img_urls = video_reader_cls(
                    video_path=str(video_path),
                    grid_size=tuple(grid_size),
                    frame_interval=frame_interval,
                    unit_width=960,
                    unit_height=540,
                    save_quality=80,
                ).run()
            else:
                log.info("未指定 grid_size，跳过缩略图生成")
        except Exception as exc:
            log.error(f"视频下载失败：{exc}")
            handle_exception(task_id, exc)
            raise

    # 下载音频
    try:
        log.info("开始下载音频")
        audio = downloader.download(
            video_url=video_url,
            quality=quality,
            output_dir=output_path,
            need_video=need_video,
        )
        audio_cache_file.write_text(
            json.dumps(asdict(audio), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info(f"音频下载并缓存成功 ({audio_cache_file})")
        return MediaDownloadResult(
            audio_meta=audio,
            video_path=video_path,
            video_img_urls=video_img_urls,
        )
    except Exception as exc:
        log.error(f"音频下载失败：{exc}")
        handle_exception(task_id, exc)
        raise
