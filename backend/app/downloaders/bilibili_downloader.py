import os
import logging
from abc import ABC
from typing import Union, Optional, List
from pathlib import Path

import yt_dlp

from app.downloaders.base import Downloader, DownloadQuality
from app.downloaders.bilibili_subtitle_resolver import (
    build_bilibili_subtitle_file,
    choose_bilibili_subtitle,
    parse_bilibili_json3_subtitle_file,
    parse_bilibili_srt_content,
)
from app.downloaders.bilibili_ytdlp_options import (
    DEFAULT_SUBTITLE_LANGS,
    build_audio_ydl_opts,
    build_subtitle_ydl_opts,
    build_video_ydl_opts,
)
from app.models.notes_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult
from app.services.bilibili_request import (
    apply_bilibili_ydl_defaults,
    resolve_bilibili_cookies_path,
)
from app.services.cookie_manager import CookieConfigManager
from app.utils.path_helper import get_data_dir
from app.utils.url_parser import extract_video_id

logger = logging.getLogger(__name__)

# B站 cookies 文件路径
BILIBILI_COOKIES_FILE = os.getenv("BILIBILI_COOKIES_FILE", "cookies.txt")
cookie_manager = CookieConfigManager()


def _bilibili_cookies_path() -> Path:
    return resolve_bilibili_cookies_path(BILIBILI_COOKIES_FILE)


def _apply_bilibili_ydl_defaults(ydl_opts: dict) -> dict:
    return apply_bilibili_ydl_defaults(
        ydl_opts,
        cookies_file=_bilibili_cookies_path(),
        cookie_getter=cookie_manager.get,
        request_logger=logger,
    )


class BilibiliDownloader(Downloader, ABC):
    def __init__(self):
        super().__init__()

    def download(
        self,
        video_url: str,
        output_dir: Union[str, None] = None,
        quality: DownloadQuality = "fast",
        need_video: Optional[bool] = False,
        skip_download: bool = False,
    ) -> AudioDownloadResult:
        if output_dir is None:
            output_dir = get_data_dir()
        if not output_dir:
            output_dir=self.cache_data
        os.makedirs(output_dir, exist_ok=True)

        output_path = os.path.join(output_dir, "%(id)s.%(ext)s")

        ydl_opts = build_audio_ydl_opts(output_path, skip_download=skip_download)
        ydl_opts = _apply_bilibili_ydl_defaults(ydl_opts)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=not skip_download)
            video_id = info.get("id")
            title = info.get("title")
            duration = info.get("duration", 0)
            cover_url = info.get("thumbnail")
            audio_path = "" if skip_download else os.path.join(output_dir, f"{video_id}.mp3")

        return AudioDownloadResult(
            file_path=audio_path,
            title=title,
            duration=duration,
            cover_url=cover_url,
            platform="bilibili",
            video_id=video_id,
            raw_info=info,
            video_path=None  # ❗音频下载不包含视频路径
        )

    def download_video(
        self,
        video_url: str,
        output_dir: Union[str, None] = None,
        resolution: Optional[str] = None,
    ) -> str:
        """
        下载视频，返回视频文件路径
        """

        if output_dir is None:
            output_dir = get_data_dir()
        os.makedirs(output_dir, exist_ok=True)
        logger.debug("解析 Bilibili 视频地址: %s", video_url)
        video_id = extract_video_id(video_url, "bilibili")
        normalized_resolution = (resolution or "best").strip() or "best"
        output_stem = video_id if normalized_resolution == "best" else f"{video_id}-{normalized_resolution}p"
        video_path = os.path.join(output_dir, f"{output_stem}.mp4")
        if os.path.exists(video_path):
            return video_path

        output_path = os.path.join(output_dir, f"{output_stem}.%(ext)s")

        ydl_opts = build_video_ydl_opts(output_path, resolution=normalized_resolution)
        ydl_opts = _apply_bilibili_ydl_defaults(ydl_opts)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(video_url, download=True)

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件未找到: {video_path}")

        return video_path

    def delete_video(self, video_path: str) -> str:
        """
        删除视频文件
        """
        if os.path.exists(video_path):
            os.remove(video_path)
            return f"视频文件已删除: {video_path}"
        else:
            return f"视频文件未找到: {video_path}"

    def download_subtitles(self, video_url: str, output_dir: str = None,
                           langs: List[str] = None) -> Optional[TranscriptResult]:
        """
        尝试获取B站视频字幕

        :param video_url: 视频链接
        :param output_dir: 输出路径
        :param langs: 优先语言列表
        :return: TranscriptResult 或 None
        """
        if output_dir is None:
            output_dir = get_data_dir()
        if not output_dir:
            output_dir = self.cache_data
        os.makedirs(output_dir, exist_ok=True)

        if langs is None:
            langs = list(DEFAULT_SUBTITLE_LANGS)

        video_id = extract_video_id(video_url, "bilibili")

        ydl_opts = build_subtitle_ydl_opts(
            output_dir=output_dir,
            video_id=video_id,
            langs=langs,
        )
        ydl_opts = _apply_bilibili_ydl_defaults(ydl_opts)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)

                # 查找下载的字幕文件
                subtitles = info.get('requested_subtitles') or {}
                if not subtitles:
                    logger.info(f"B站视频 {video_id} 没有可用字幕")
                    return None

                selection = choose_bilibili_subtitle(subtitles, langs)
                if not selection:
                    logger.info(f"B站视频 {video_id} 没有可用字幕（排除弹幕）")
                    return None

                detected_lang = selection.language
                sub_info = selection.info

                # 检查是否有内嵌数据（yt-dlp 有时直接返回字幕内容）
                if 'data' in sub_info and sub_info['data']:
                    logger.info(f"直接从返回数据解析字幕: {detected_lang}")
                    return self._parse_srt_content(sub_info['data'], detected_lang)

                # 查找字幕文件
                ext = sub_info.get('ext', 'srt')
                subtitle_file = build_bilibili_subtitle_file(
                    output_dir,
                    video_id,
                    detected_lang,
                    sub_info,
                )

                if not os.path.exists(subtitle_file):
                    logger.info(f"字幕文件不存在: {subtitle_file}")
                    return None

                # 根据格式解析字幕文件
                if ext == 'json3':
                    return self._parse_json3_subtitle(subtitle_file, detected_lang)
                else:
                    with open(subtitle_file, 'r', encoding='utf-8') as f:
                        return self._parse_srt_content(f.read(), detected_lang)

        except Exception as e:
            logger.warning(f"获取B站字幕失败: {e}")
            return None

    def _parse_srt_content(self, srt_content: str, language: str) -> Optional[TranscriptResult]:
        """
        解析 SRT 格式字幕内容

        :param srt_content: SRT 字幕文本内容
        :param language: 语言代码
        :return: TranscriptResult
        """
        return parse_bilibili_srt_content(
            srt_content,
            language,
            request_logger=logger,
        )

    def _parse_json3_subtitle(self, subtitle_file: str, language: str) -> Optional[TranscriptResult]:
        """
        解析 json3 格式字幕文件

        :param subtitle_file: 字幕文件路径
        :param language: 语言代码
        :return: TranscriptResult
        """
        return parse_bilibili_json3_subtitle_file(
            subtitle_file,
            language,
            request_logger=logger,
        )
