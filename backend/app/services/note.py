import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple, Union, Any

from pydantic import HttpUrl
from dotenv import load_dotenv

from app.downloaders.base import Downloader
from app.db.video_task_dao import delete_task_by_task_id, delete_task_by_video, insert_video_task
from app.enmus.exception import NoteErrorEnum
from app.enmus.task_status_enums import TaskStatus
from app.enmus.note_enums import DownloadQuality
from app.exceptions.note import NoteError
from app.gpt.base import GPT
from app.models.notes_model import AudioDownloadResult, NoteResult
from app.models.transcriber_model import TranscriptResult
from app.services.constant import SUPPORT_PLATFORM_MAP
from app.services.progress_state import cancel_task, is_task_cancel_requested, write_task_status
from app.services import note_gpt_provider
from app.services import note_completion
from app.services import note_generation_plan
from app.services import note_llm_markdown
from app.services import note_markdown_postprocess
from app.services import note_media_download
from app.services import note_result_payload
from app.services import note_transcript_source
from app.services import subtitle_audio_meta
from app.services import subtitle_transcripts
from app.services.task_runtime import default_note_output_dir
from app.services import transcript_markdown
from app.utils.screenshot_marker import extract_screenshot_timestamps

# ------------------ 环境变量与全局配置 ------------------

# 从 .env 文件中加载环境变量
load_dotenv()

# 后端 API 地址与端口（若有需要可以在代码其他部分使用 BACKEND_BASE_URL）
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost")
BACKEND_PORT = os.getenv("BACKEND_PORT", "8483")
BACKEND_BASE_URL = f"{API_BASE_URL}:{BACKEND_PORT}"

# 输出目录（用于缓存音频、转写、Markdown 文件，以及存储截图）
NOTE_OUTPUT_DIR = default_note_output_dir()
NOTE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_OUTPUT_DIR = os.getenv("OUT_DIR", "./static/screenshots")
# 图片基础 URL（用于生成 Markdown 中的图片链接，需前端静态目录对应）
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "/static/screenshots")

# 日志配置
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class TaskCancelledError(RuntimeError):
    pass


class NoteGenerator:
    """
    NoteGenerator 用于执行视频/音频下载、转写、GPT 生成笔记、插入截图/链接、
    以及将任务信息写入状态文件与数据库等功能。
    """
    SUBTITLE_REQUIRED_MESSAGE = "当前仅支持平台字幕生成，未找到可用字幕文件。"
    SUBTITLE_TRANSCRIPT_SOURCES = subtitle_transcripts.SUBTITLE_TRANSCRIPT_SOURCES

    def __init__(self):
        self.video_path: Optional[Path] = None
        self.video_img_urls = []
        logger.info("NoteGenerator 初始化完成")


    # ---------------- 公有方法 ----------------

    def generate(
        self,
        video_url: Union[str, HttpUrl],
        platform: str,
        quality: DownloadQuality = DownloadQuality.medium,
        task_id: Optional[str] = None,
        model_name: Optional[str] = None,
        provider_id: Optional[str] = None,
        link: bool = False,
        screenshot: bool = False,
        _format: Optional[List[str]] = None,
        style: Optional[str] = None,
        extras: Optional[str] = None,
        output_path: Optional[str] = None,
        video_understanding: bool = False,
        video_interval: int = 0,
        grid_size: Optional[List[int]] = None,
        mode: str = "note",
    ) -> NoteResult | None:
        """
        主流程：按步骤依次下载、转写、GPT 总结、截图/链接处理、存库、返回 NoteResult。

        :param video_url: 视频或音频链接
        :param platform: 平台名称，对应 SUPPORT_PLATFORM_MAP 中的键
        :param quality: 下载音频的质量枚举
        :param task_id: 用于标识本次任务的唯一 ID，亦用于状态文件和缓存文件命名
        :param model_name: GPT 模型名称
        :param provider_id: 模型供应商 ID
        :param link: 是否在笔记中插入视频片段链接
        :param screenshot: 是否在笔记中替换 Screenshot 标记为图片
        :param _format: 包含 'link' 或 'screenshot' 等字符串的列表，决定后续处理
        :param style: GPT 生成笔记的风格
        :param extras: 额外参数，传递给 GPT
        :param output_path: 下载输出目录（可选）
        :param video_understanding: 是否需要视频拼图理解（生成缩略图）
        :param video_interval: 视频帧截取间隔（秒），仅在 video_understanding 为 True 时生效
        :param grid_size: 生成缩略图时的网格大小，如 [3, 3]
        :param mode: 生成模式，"note" 为 AI 笔记，"transcript" 为仅转写文字稿，
            "polished_transcript" 为大模型校对文字稿
        :return: NoteResult 对象，包含 markdown 文本、转写结果和音频元信息
        """
        if grid_size is None:
            grid_size = []
        mode_branch = note_generation_plan.prepare_mode_branch(mode)

        try:
            logger.info(f"开始生成笔记 (task_id={task_id})")
            self._cancel_if_requested(task_id)
            self._update_status(task_id, TaskStatus.PARSING, platform=platform)

            # 获取下载器与 GPT 实例

            downloader = self._get_downloader(platform)
            self._cancel_if_requested(task_id)
            gpt = None

            cache_paths = note_generation_plan.build_cache_paths(NOTE_OUTPUT_DIR, task_id)
            # 1. 获取字幕/转写：优先缓存 → 平台字幕 → 音频转写
            transcript = note_transcript_source.load_or_download_platform_transcript(
                transcript_cache_file=cache_paths.transcript_cache_file,
                downloader=downloader,
                video_url=video_url,
                log=logger,
            )

            # 2. 下载音频/视频
            # 有字幕时只提取元信息，不下载音视频文件（除非需要截图/视频理解）
            has_transcript = transcript is not None
            if not has_transcript:
                raise RuntimeError(self.SUBTITLE_REQUIRED_MESSAGE)
            self._cancel_if_requested(task_id)

            media_plan = note_generation_plan.prepare_media_source(
                platform=platform,
                screenshot=screenshot,
                video_understanding=video_understanding,
            )
            if media_plan.use_subtitle_only_audio_meta:
                logger.info("YouTube 已获取字幕，跳过媒体探测，直接构造字幕元信息")
                audio_meta = self._build_subtitle_only_audio_meta(
                    video_url=video_url,
                    platform=platform,
                    transcript=transcript,
                )
                note_generation_plan.write_audio_cache(cache_paths.audio_cache_file, audio_meta)
            else:
                audio_meta = self._download_media(
                    downloader=downloader,
                    video_url=video_url,
                    quality=quality,
                    audio_cache_file=cache_paths.audio_cache_file,
                    status_phase=TaskStatus.DOWNLOADING,
                    platform=platform,
                    output_path=output_path,
                    screenshot=screenshot,
                    video_understanding=video_understanding,
                    video_interval=video_interval,
                    grid_size=grid_size,
                    skip_download=media_plan.skip_download,
                )
            self._cancel_if_requested(task_id)

            if mode_branch.is_transcript_only:
                markdown = self._build_transcript_markdown(audio_meta=audio_meta, transcript=transcript)
                cache_paths.markdown_cache_file.write_text(markdown, encoding="utf-8")

                self._cancel_if_requested(task_id)
                return self._complete_generation(
                    task_id=task_id,
                    markdown=markdown,
                    video_url=video_url,
                    transcript=transcript,
                    audio_meta=audio_meta,
                    platform=platform,
                    success_message="文字稿生成成功",
                )

            if mode_branch.is_polished_transcript:
                gpt = self._get_gpt(model_name, provider_id)
                markdown = self._polish_transcript(
                    audio_meta=audio_meta,
                    transcript=transcript,
                    gpt=gpt,
                    markdown_cache_file=cache_paths.markdown_cache_file,
                )
                self._cancel_if_requested(task_id)

                return self._complete_generation(
                    task_id=task_id,
                    markdown=markdown,
                    video_url=video_url,
                    transcript=transcript,
                    audio_meta=audio_meta,
                    platform=platform,
                    success_message="校对文字稿生成成功",
                )

            # 3. GPT 总结
            gpt = self._get_gpt(model_name, provider_id)
            markdown = self._summarize_text(
                audio_meta=audio_meta,
                transcript=transcript,
                gpt=gpt,
                markdown_cache_file=cache_paths.markdown_cache_file,
                link=link,
                screenshot=screenshot,
                formats=_format or [],
                style=style,
                extras=extras,
                video_img_urls=self.video_img_urls,
            )
            self._cancel_if_requested(task_id)

            # 4. 截图 & 链接替换
            if _format:
                markdown = self._post_process_markdown(
                    markdown=markdown,
                    video_path=self.video_path,
                    formats=_format,
                    audio_meta=audio_meta,
                    platform=platform,
                )

            # 5. 保存记录到数据库
            self._cancel_if_requested(task_id)
            return self._complete_generation(
                task_id=task_id,
                markdown=markdown,
                video_url=video_url,
                transcript=transcript,
                audio_meta=audio_meta,
                platform=platform,
                success_message="笔记生成成功",
            )

        except TaskCancelledError as exc:
            logger.info(f"任务已取消 (task_id={task_id})：{exc}")
            return None
        except Exception as exc:
            logger.error(f"生成笔记流程异常 (task_id={task_id})：{exc}", exc_info=True)
            self._update_status(task_id, TaskStatus.FAILED, message=str(exc), platform=platform)
            return None

    @staticmethod
    def _is_subtitle_transcript_data(data: dict) -> bool:
        return subtitle_transcripts.is_subtitle_transcript_data(data)

    @staticmethod
    def _is_subtitle_transcript_result(transcript: TranscriptResult) -> bool:
        return subtitle_transcripts.is_subtitle_transcript_result(transcript)

    @staticmethod
    def _load_transcript_cache(
        transcript_cache_file: Path,
    ) -> Optional[TranscriptResult]:
        return subtitle_transcripts.load_subtitle_transcript_cache(
            transcript_cache_file,
            log=logger,
        )

    @staticmethod
    def delete_note(video_id: Optional[str] = None, platform: Optional[str] = None, task_id: Optional[str] = None) -> int:
        """
        删除数据库中的任务记录

        :param video_id: 视频 ID
        :param platform: 平台标识
        :param task_id: 任务 ID
        :return: 删除的记录数
        """
        if task_id:
            logger.info(f"删除笔记记录 (task_id={task_id})")
            return delete_task_by_task_id(task_id)

        if not video_id or not platform:
            logger.warning("删除笔记记录失败：缺少 task_id，且未提供完整的 video_id/platform")
            return 0

        logger.info(f"删除笔记记录 (video_id={video_id}, platform={platform})")
        return delete_task_by_video(video_id, platform)

    # ---------------- 私有方法 ----------------

    def _get_gpt(self, model_name: Optional[str], provider_id: Optional[str]) -> GPT:
        """
        根据 provider_id 获取对应的 GPT 实例
        :param model_name: GPT 模型名称
        :param provider_id: 供应商 ID
        :return: GPT 实例
        """
        return note_gpt_provider.build_gpt(model_name, provider_id, log=logger)

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        return transcript_markdown.format_timestamp(seconds)

    @staticmethod
    def _simplify_chinese(text: str) -> str:
        return transcript_markdown.simplify_chinese(text)

    @staticmethod
    def _normalize_transcript_text(text: str) -> str:
        return transcript_markdown.normalize_transcript_text(text)

    @staticmethod
    def _build_transcript_markdown(audio_meta: AudioDownloadResult, transcript: TranscriptResult) -> str:
        return transcript_markdown.build_transcript_markdown(audio_meta, transcript)

    @staticmethod
    def _build_note_result(
        markdown: str,
        video_url: Union[str, HttpUrl],
        transcript: TranscriptResult,
        audio_meta: AudioDownloadResult,
    ) -> NoteResult:
        return note_result_payload.build_note_result(
            markdown=markdown,
            video_url=video_url,
            transcript=transcript,
            audio_meta=audio_meta,
        )

    def _complete_generation(
        self,
        *,
        task_id: Optional[str],
        markdown: str,
        video_url: Union[str, HttpUrl],
        transcript: TranscriptResult,
        audio_meta: AudioDownloadResult,
        platform: str,
        success_message: str,
    ) -> NoteResult:
        return note_completion.complete_note_generation(
            task_id=task_id,
            markdown=markdown,
            video_url=video_url,
            transcript=transcript,
            audio_meta=audio_meta,
            platform=platform,
            success_message=success_message,
            update_status=self._update_status,
            save_metadata=self._save_metadata,
            log=logger,
        )

    @staticmethod
    def _build_subtitle_only_audio_meta(
        video_url: Union[str, HttpUrl],
        platform: str,
        transcript: TranscriptResult,
    ) -> AudioDownloadResult:
        return subtitle_audio_meta.build_subtitle_only_audio_meta(
            video_url=video_url,
            platform=platform,
            transcript=transcript,
            title_lookup=NoteGenerator._fetch_video_title,
        )

    @staticmethod
    def _fetch_video_title(video_url: str, platform: str) -> str | None:
        return subtitle_audio_meta.fetch_video_title(video_url, platform)

    def _polish_transcript(
        self,
        audio_meta: AudioDownloadResult,
        transcript: TranscriptResult,
        gpt: GPT,
        markdown_cache_file: Path,
    ) -> str:
        task_id = markdown_cache_file.stem
        self._update_status(task_id, TaskStatus.SUMMARIZING)
        return note_llm_markdown.polish_transcript_markdown(
            audio_meta=audio_meta,
            transcript=transcript,
            gpt=gpt,
            markdown_cache_file=markdown_cache_file,
        )

    def _get_downloader(self, platform: str) -> Downloader:
        """
        根据平台名称获取对应的下载器实例

        :param platform: 平台标识，需在 SUPPORT_PLATFORM_MAP 中
        :return: 对应的 Downloader 子类实例
        """
        downloader_cls = SUPPORT_PLATFORM_MAP.get(platform)
        logger.debug(f"实例化下载器 -  {platform}")
        instance = None
        if not downloader_cls:
            logger.error(f"不支持的平台：{platform}")
            raise NoteError(code=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.code,
                            message=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.message)
        try:
            instance = downloader_cls
        except Exception as e:
            logger.error(f"实例化下载器失败：{e}")


        logger.info(f"使用下载器：{downloader_cls.__class__}")
        return instance

    @staticmethod
    def _update_status(
        task_id: Optional[str],
        status: Union[str, TaskStatus],
        message: Optional[str] = None,
        title: Optional[str] = None,
        platform: Optional[str] = None,
    ):
        """
        创建或更新 {task_id}.status.json，记录当前任务状态

        :param task_id: 任务唯一 ID
        :param status: TaskStatus 枚举或自定义状态字符串
        :param message: 可选消息，用于记录失败原因等
        """
        if not task_id:
            return

        try:
            payload = NoteGenerator._build_status_payload(
                task_id=task_id,
                status=status,
                message=message,
                title=title,
                platform=platform,
            )
            write_task_status(
                task_id=payload["task_id"],
                output_dir=NOTE_OUTPUT_DIR,
                status=payload["status"],
                message=payload["message"],
                title=payload["title"],
                platform=payload["platform"],
            )
        except Exception as e:
            logger.error(f"写入状态文件失败 (task_id={task_id})：{e}")

    @staticmethod
    def _build_status_payload(
        task_id: str,
        status: Union[str, TaskStatus],
        message: Optional[str] = None,
        title: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> dict:
        return note_result_payload.build_status_payload(
            task_id=task_id,
            status=status,
            message=message,
            title=title,
            platform=platform,
        )

    @staticmethod
    def _cancel_if_requested(task_id: Optional[str]) -> None:
        if not task_id:
            return

        if not is_task_cancel_requested(task_id=task_id, output_dir=NOTE_OUTPUT_DIR):
            return

        cancel_task(task_id=task_id, output_dir=NOTE_OUTPUT_DIR)
        raise TaskCancelledError('任务已取消')

    def _handle_exception(self, task_id, exc):
        logger.error(f"任务异常 (task_id={task_id})", exc_info=True)
        self._update_status(task_id, TaskStatus.FAILED, message=self._format_exception_message(exc))

    @staticmethod
    def _format_exception_message(exc: Exception) -> str:
        return note_result_payload.format_exception_message(exc)

    def _download_media(
        self,
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
        skip_download: bool = False,
    ) -> AudioDownloadResult | None:
        """
        1. 检查音频缓存；若不存在，则根据需要下载音频或视频（若需截图/可视化）。
        2. 如果需要视频，则先下载视频并生成缩略图集，再下载音频。
        3. 返回 AudioDownloadResult

        :param downloader: Downloader 实例
        :param video_url: 视频/音频链接
        :param quality: 音频下载质量
        :param audio_cache_file: 本地缓存 JSON 文件路径
        :param status_phase: 对应的状态枚举，如 TaskStatus.DOWNLOADING
        :param platform: 平台标识
        :param output_path: 下载输出目录（可为 None）
        :param screenshot: 是否需要在笔记中插入截图
        :param video_understanding: 是否需要生成缩略图
        :param video_interval: 视频截帧间隔
        :param grid_size: 缩略图网格尺寸
        :return: AudioDownloadResult 对象
        """
        result = note_media_download.download_media(
            downloader=downloader,
            video_url=video_url,
            quality=quality,
            audio_cache_file=audio_cache_file,
            status_phase=status_phase,
            platform=platform,
            output_path=output_path,
            screenshot=screenshot,
            video_understanding=video_understanding,
            video_interval=video_interval,
            grid_size=grid_size,
            update_status=self._update_status,
            handle_exception=self._handle_exception,
            skip_download=skip_download,
            log=logger,
        )
        self.video_path = result.video_path
        self.video_img_urls = result.video_img_urls
        return result.audio_meta

    def _summarize_text(
        self,
        audio_meta: AudioDownloadResult,
        transcript: TranscriptResult,
        gpt: GPT,
        markdown_cache_file: Path,
        link: bool,
        screenshot: bool,
        formats: List[str],
        style: Optional[str],
        extras: Optional[str],
        video_img_urls: List[str],
    ) -> str | None:
        """
        调用 GPT 对转写结果进行总结，生成 Markdown 文本并缓存。

        :param audio_meta: AudioDownloadResult 元信息
        :param transcript: TranscriptResult 转写结果
        :param gpt: GPT 实例
        :param markdown_cache_file: Markdown 缓存路径
        :param link: 是否在笔记中插入链接
        :param screenshot: 是否在笔记中生成截图占位
        :param formats: 包含 'link' 或 'screenshot' 的列表
        :param style: GPT 输出风格
        :param extras: GPT 额外参数
        :return: 生成的 Markdown 字符串
        """
        task_id = markdown_cache_file.stem
        self._update_status(task_id, TaskStatus.SUMMARIZING)

        try:
            return note_llm_markdown.summarize_note_markdown(
                audio_meta=audio_meta,
                transcript=transcript,
                gpt=gpt,
                markdown_cache_file=markdown_cache_file,
                link=link,
                screenshot=screenshot,
                formats=formats,
                style=style,
                extras=extras,
                video_img_urls=video_img_urls,
            )
        except Exception as exc:
            logger.error(f"GPT 总结失败：{exc}")
            self._handle_exception(task_id, exc)
            raise

    def _post_process_markdown(
        self,
        markdown: str,
        video_path: Optional[Path],
        formats: List[str],
        audio_meta: AudioDownloadResult,
        platform: str,
    ) -> str:
        """
        对生成的 Markdown 做后期处理：插入截图和/或插入链接。

        :param markdown: 原始 Markdown 字符串
        :param video_path: 本地视频路径（可为 None）
        :param formats: 包含 'link' 或 'screenshot' 的列表
        :param audio_meta: AudioDownloadResult 元信息，用于链接替换
        :param platform: 平台标识，用于链接替换
        :return: 处理后的 Markdown 字符串
        """
        return note_markdown_postprocess.post_process_markdown(
            markdown=markdown,
            video_path=video_path,
            formats=formats,
            audio_meta=audio_meta,
            platform=platform,
            insert_screenshots=self._insert_screenshots,
            log=logger,
        )

    def _insert_screenshots(self, markdown: str, video_path: Path) -> str | None | Any:
        """
        扫描 Markdown 文本中所有 Screenshot 标记，并替换为实际生成的截图链接。

        :param markdown: 含有 *Screenshot-mm:ss 或 Screenshot-[mm:ss] 标记的 Markdown 文本
        :param video_path: 本地视频文件路径
        :return: 替换后的 Markdown 字符串
        """
        return note_markdown_postprocess.insert_screenshots(
            markdown,
            video_path,
            image_output_dir=str(IMAGE_OUTPUT_DIR),
            image_base_url=IMAGE_BASE_URL,
            log=logger,
        )

    @staticmethod
    def _extract_screenshot_timestamps(markdown: str) -> List[Tuple[str, int]]:
        """
        从 Markdown 文本中提取所有 '*Screenshot-mm:ss' 或 'Screenshot-[mm:ss]' 标记，
        返回 [(原始标记文本, 时间戳秒数), ...] 列表。

        :param markdown: 原始 Markdown 文本
        :return: 标记与对应时间戳秒数的列表
        """
        return extract_screenshot_timestamps(markdown)

    def _save_metadata(self, video_id: str, platform: str, task_id: str) -> None:
        """
        将生成的笔记任务记录插入数据库

        :param video_id: 视频 ID
        :param platform: 平台标识
        :param task_id: 任务 ID
        """
        try:
            insert_video_task(video_id=video_id, platform=platform, task_id=task_id)
            logger.info(f"已保存任务记录到数据库 (video_id={video_id}, platform={platform}, task_id={task_id})")
        except Exception as e:
            logger.error(f"保存任务记录失败：{e}")
