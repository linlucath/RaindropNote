import json
import logging
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Tuple, Union, Any

from fastapi import HTTPException
from pydantic import HttpUrl
from dotenv import load_dotenv

from app.downloaders.base import Downloader
from app.downloaders.bilibili_downloader import BilibiliDownloader
from app.downloaders.douyin_downloader import DouyinDownloader
from app.downloaders.local_downloader import LocalDownloader
from app.downloaders.youtube_downloader import YoutubeDownloader
from app.db.video_task_dao import delete_task_by_task_id, delete_task_by_video, insert_video_task
from app.enmus.exception import NoteErrorEnum, ProviderErrorEnum
from app.enmus.task_status_enums import TaskStatus
from app.enmus.note_enums import DownloadQuality
from app.exceptions.note import NoteError
from app.exceptions.provider import ProviderError
from app.gpt.base import GPT
from app.gpt.gpt_factory import GPTFactory
from app.models.audio_model import AudioDownloadResult
from app.models.gpt_model import GPTSource
from app.models.model_config import ModelConfig
from app.models.notes_model import AudioDownloadResult, NoteResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services.constant import SUPPORT_PLATFORM_MAP
from app.services.progress_state import cancel_task, is_task_cancel_requested, write_task_status
from app.services.provider import ProviderService
from app.transcriber.base import Transcriber
from app.utils.note_helper import replace_content_markers, prepend_source_link
from app.utils.screenshot_marker import extract_screenshot_timestamps
from app.utils.status_code import StatusCode
from app.utils.video_helper import generate_screenshot
from app.utils.video_reader import VideoReader

# ------------------ 环境变量与全局配置 ------------------

# 从 .env 文件中加载环境变量
load_dotenv()

# 后端 API 地址与端口（若有需要可以在代码其他部分使用 BACKEND_BASE_URL）
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost")
BACKEND_PORT = os.getenv("BACKEND_PORT", "8483")
BACKEND_BASE_URL = f"{API_BASE_URL}:{BACKEND_PORT}"

# 输出目录（用于缓存音频、转写、Markdown 文件，以及存储截图）
NOTE_OUTPUT_DIR = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
NOTE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_OUTPUT_DIR = os.getenv("OUT_DIR", "./static/screenshots")
# 图片基础 URL（用于生成 Markdown 中的图片链接，需前端静态目录对应）
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL", "/static/screenshots")

# 日志配置
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class TaskCancelledError(RuntimeError):
    pass


def _get_transcriber_registry():
    from app.transcriber.transcriber_provider import _transcribers

    return _transcribers


def _get_configured_transcriber(transcriber_type: str, model_size: str):
    from app.transcriber.transcriber_provider import get_transcriber

    return get_transcriber(transcriber_type=transcriber_type, model_size=model_size)


class NoteGenerator:
    """
    NoteGenerator 用于执行视频/音频下载、转写、GPT 生成笔记、插入截图/链接、
    以及将任务信息写入状态文件与数据库等功能。
    """
    AUDIO_TRANSCRIPTION_CONFIRMATION_MESSAGE = (
        "未找到可用字幕文件。需要确认音频转写后，才会下载音频并进行转写。"
    )
    SUBTITLE_TRANSCRIPT_SOURCES = {"bilibili_subtitle", "youtube_transcript_api"}

    def __init__(self):
        from app.services.transcriber_config_manager import TranscriberConfigManager
        config_manager = TranscriberConfigManager()
        self.model_size: str = config_manager.get_whisper_model_size()
        self.device: Optional[str] = None
        self.transcriber_type: str = config_manager.get_transcriber_type()
        self.transcriber: Transcriber = self._init_transcriber()
        self.video_path: Optional[Path] = None
        self.video_img_urls=[]
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
        allow_audio_transcription: bool = False,
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
        :param allow_audio_transcription: 无字幕时是否允许下载音频并转写
        :return: NoteResult 对象，包含 markdown 文本、转写结果和音频元信息
        """
        if grid_size is None:
            grid_size = []
        is_transcript_only = mode == "transcript"
        is_polished_transcript = mode == "polished_transcript"

        try:
            logger.info(f"开始生成笔记 (task_id={task_id})")
            self._cancel_if_requested(task_id)
            self._update_status(task_id, TaskStatus.PARSING, platform=platform)

            # 获取下载器与 GPT 实例

            downloader = self._get_downloader(platform)
            self._cancel_if_requested(task_id)
            gpt = None

            # 缓存文件路径
            audio_cache_file = NOTE_OUTPUT_DIR / f"{task_id}_audio.json"
            transcript_cache_file = NOTE_OUTPUT_DIR / f"{task_id}_transcript.json"
            markdown_cache_file = NOTE_OUTPUT_DIR / f"{task_id}_markdown.md"
            # 1. 获取字幕/转写：优先缓存 → 平台字幕 → 音频转写
            transcript = None

            # 尝试读取缓存
            if transcript_cache_file.exists():
                logger.info(f"检测到转写缓存 ({transcript_cache_file})，尝试读取")
                try:
                    transcript = self._load_transcript_cache(
                        transcript_cache_file,
                        allow_audio_transcription=allow_audio_transcription,
                    )
                    if transcript:
                        logger.info(f"已从缓存加载转写结果，共 {len(transcript.segments)} 段")
                except Exception as e:
                    logger.warning(f"加载转写缓存失败: {e}")

            # 缓存没有，尝试获取平台字幕
            if transcript is None:
                logger.info("尝试获取平台字幕（优先于音频下载）...")
                try:
                    transcript = downloader.download_subtitles(video_url)
                    if transcript and transcript.segments:
                        logger.info(f"成功获取平台字幕，共 {len(transcript.segments)} 段")
                        transcript_cache_file.write_text(
                            json.dumps(asdict(transcript), ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                    else:
                        transcript = None
                        logger.info("平台无可用字幕")
                except Exception as e:
                    logger.warning(f"获取平台字幕失败: {e}")
                    transcript = None

            # 2. 下载音频/视频
            # 有字幕时只提取元信息，不下载音视频文件（除非需要截图/视频理解）
            has_transcript = transcript is not None
            if not has_transcript and not allow_audio_transcription:
                raise RuntimeError(self.AUDIO_TRANSCRIPTION_CONFIRMATION_MESSAGE)

            need_full_download = not has_transcript or screenshot or video_understanding
            audio_meta = self._download_media(
                downloader=downloader,
                video_url=video_url,
                quality=quality,
                audio_cache_file=audio_cache_file,
                status_phase=TaskStatus.DOWNLOADING,
                platform=platform,
                output_path=output_path,
                screenshot=screenshot,
                video_understanding=video_understanding,
                video_interval=video_interval,
                grid_size=grid_size,
                skip_download=not need_full_download,
            )
            self._cancel_if_requested(task_id)

            # 3. 如果前面没拿到字幕，走转写流程
            if transcript is None:
                transcript = self._get_transcript(
                    downloader=downloader,
                    video_url=video_url,
                    audio_file=audio_meta.file_path,
                    transcript_cache_file=transcript_cache_file,
                    status_phase=TaskStatus.TRANSCRIBING,
                    task_id=task_id,
                    allow_audio_transcription=allow_audio_transcription,
                )
            self._cancel_if_requested(task_id)

            if is_transcript_only:
                markdown = self._build_transcript_markdown(audio_meta=audio_meta, transcript=transcript)
                markdown_cache_file.write_text(markdown, encoding="utf-8")
                markdown = prepend_source_link(markdown, str(video_url))

                self._cancel_if_requested(task_id)
                self._update_status(task_id, TaskStatus.SAVING, title=audio_meta.title, platform=platform)
                self._save_metadata(video_id=audio_meta.video_id, platform=platform, task_id=task_id)

                self._update_status(task_id, TaskStatus.SUCCESS, title=audio_meta.title, platform=platform)
                logger.info(f"文字稿生成成功 (task_id={task_id})")
                return NoteResult(markdown=markdown, transcript=transcript, audio_meta=audio_meta)

            if is_polished_transcript:
                gpt = self._get_gpt(model_name, provider_id)
                markdown = self._polish_transcript(
                    audio_meta=audio_meta,
                    transcript=transcript,
                    gpt=gpt,
                    markdown_cache_file=markdown_cache_file,
                )
                self._cancel_if_requested(task_id)
                markdown = prepend_source_link(markdown, str(video_url))

                self._cancel_if_requested(task_id)
                self._update_status(task_id, TaskStatus.SAVING, title=audio_meta.title, platform=platform)
                self._save_metadata(video_id=audio_meta.video_id, platform=platform, task_id=task_id)

                self._update_status(task_id, TaskStatus.SUCCESS, title=audio_meta.title, platform=platform)
                logger.info(f"校对文字稿生成成功 (task_id={task_id})")
                return NoteResult(markdown=markdown, transcript=transcript, audio_meta=audio_meta)

            # 3. GPT 总结
            gpt = self._get_gpt(model_name, provider_id)
            markdown = self._summarize_text(
                audio_meta=audio_meta,
                transcript=transcript,
                gpt=gpt,
                markdown_cache_file=markdown_cache_file,
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

            markdown = prepend_source_link(markdown, str(video_url))

            # 5. 保存记录到数据库
            self._cancel_if_requested(task_id)
            self._update_status(task_id, TaskStatus.SAVING, title=audio_meta.title, platform=platform)
            self._save_metadata(video_id=audio_meta.video_id, platform=platform, task_id=task_id)

            # 6. 完成
            self._update_status(task_id, TaskStatus.SUCCESS, title=audio_meta.title, platform=platform)
            logger.info(f"笔记生成成功 (task_id={task_id})")
            return NoteResult(markdown=markdown, transcript=transcript, audio_meta=audio_meta)

        except TaskCancelledError as exc:
            logger.info(f"任务已取消 (task_id={task_id})：{exc}")
            return None
        except Exception as exc:
            logger.error(f"生成笔记流程异常 (task_id={task_id})：{exc}", exc_info=True)
            self._update_status(task_id, TaskStatus.FAILED, message=str(exc), platform=platform)
            return None

    @staticmethod
    def _is_subtitle_transcript_data(data: dict) -> bool:
        raw = data.get("raw") or {}
        return isinstance(raw, dict) and raw.get("source") in NoteGenerator.SUBTITLE_TRANSCRIPT_SOURCES

    @staticmethod
    def _is_subtitle_transcript_result(transcript: TranscriptResult) -> bool:
        raw = transcript.raw or {}
        return isinstance(raw, dict) and raw.get("source") in NoteGenerator.SUBTITLE_TRANSCRIPT_SOURCES

    @staticmethod
    def _load_transcript_cache(
        transcript_cache_file: Path,
        allow_audio_transcription: bool = False,
    ) -> Optional[TranscriptResult]:
        data = json.loads(transcript_cache_file.read_text(encoding="utf-8"))
        if not allow_audio_transcription and not NoteGenerator._is_subtitle_transcript_data(data):
            logger.info(f"转写缓存不是字幕来源，等待用户确认音频转写 ({transcript_cache_file})")
            return None

        segments = [TranscriptSegment(**seg) for seg in data.get("segments", [])]
        return TranscriptResult(
            language=data.get("language"),
            full_text=data["full_text"],
            segments=segments,
            raw=data.get("raw"),
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

    def _init_transcriber(self) -> Transcriber:
        """
        根据环境变量 TRANSCRIBER_TYPE 动态获取并实例化转写器
        """
        _transcribers = _get_transcriber_registry()
        if self.transcriber_type not in _transcribers:
            logger.error(f"未找到支持的转写器：{self.transcriber_type}")
            raise Exception(f"不支持的转写器：{self.transcriber_type}")

        logger.info(f"使用转写器：{self.transcriber_type}")
        return _get_configured_transcriber(
            transcriber_type=self.transcriber_type,
            model_size=self.model_size,
        )

    def _get_gpt(self, model_name: Optional[str], provider_id: Optional[str]) -> GPT:
        """
        根据 provider_id 获取对应的 GPT 实例
        :param model_name: GPT 模型名称
        :param provider_id: 供应商 ID
        :return: GPT 实例
        """
        provider = ProviderService.get_provider_by_id(provider_id)
        if not provider:
            logger.error(f"[get_gpt] 未找到模型供应商: provider_id={provider_id}")
            raise ProviderError(code=ProviderErrorEnum.NOT_FOUND,message=ProviderErrorEnum.NOT_FOUND.message)
        logger.info(f"创建 GPT 实例 {provider_id}")
        config = ModelConfig(
            api_key=provider["api_key"],
            base_url=provider["base_url"],
            model_name=model_name,
            provider=provider["type"],
            name=provider["name"],
        )
        return GPTFactory().from_config(config)

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        total_seconds = int(seconds or 0)
        minutes, secs = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def _simplify_chinese(text: str) -> str:
        if not text:
            return ""

        try:
            from opencc import OpenCC
            return OpenCC("t2s").convert(text)
        except Exception:
            phrase_map = {
                "視頻": "视频",
            }
            for source, target in phrase_map.items():
                text = text.replace(source, target)
            fallback_map = str.maketrans({
                "這": "这", "個": "个", "視": "视", "頻": "频",
                "學": "学", "習": "习", "後": "后", "還": "还", "補": "补",
                "觀": "观", "點": "点", "測": "测", "試": "试", "裏": "里",
                "裡": "里", "與": "与", "為": "为", "會": "会", "說": "说",
                "講": "讲", "讓": "让", "對": "对", "開": "开", "關": "关",
                "題": "题", "體": "体", "現": "现", "實": "实", "應": "应",
                "產": "产", "業": "业", "經": "经", "營": "营", "專": "专",
                "區": "区", "並": "并", "從": "从", "變": "变", "種": "种",
                "時": "时", "間": "间", "線": "线", "錄": "录", "轉": "转",
                "寫": "写", "長": "长", "標": "标", "簡": "简", "體": "体",
            })
            return text.translate(fallback_map)

    @staticmethod
    def _normalize_transcript_text(text: str) -> str:
        simplified = NoteGenerator._simplify_chinese(text.strip())
        simplified = re.sub(r"\s+", " ", simplified)
        simplified = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", simplified)
        return simplified

    @staticmethod
    def _build_transcript_markdown(audio_meta: AudioDownloadResult, transcript: TranscriptResult) -> str:
        title = NoteGenerator._normalize_transcript_text(audio_meta.title or "未命名视频")
        segment_texts = [
            NoteGenerator._normalize_transcript_text(segment.text)
            for segment in transcript.segments
            if segment.text and segment.text.strip()
        ]
        readable_text = NoteGenerator._normalize_transcript_text("".join(segment_texts))
        timestamp_lines = [
            f"[{NoteGenerator._format_timestamp(segment.start)}] {NoteGenerator._normalize_transcript_text(segment.text)}"
            for segment in transcript.segments
            if segment.text and segment.text.strip()
        ]

        return "\n\n".join([
            f"# {title}",
            "## 简体中文文字稿",
            readable_text or NoteGenerator._normalize_transcript_text(transcript.full_text or ""),
            "## 带时间戳文字稿",
            "\n".join(timestamp_lines),
        ]).strip()

    def _polish_transcript(
        self,
        audio_meta: AudioDownloadResult,
        transcript: TranscriptResult,
        gpt: GPT,
        markdown_cache_file: Path,
    ) -> str:
        task_id = markdown_cache_file.stem
        self._update_status(task_id, TaskStatus.SUMMARIZING)

        source = GPTSource(
            title=audio_meta.title,
            segment=transcript.segments,
            tags=audio_meta.raw_info.get("tags", []),
            checkpoint_key=task_id,
        )
        polished_text = gpt.polish_transcript(source).strip()
        title = self._normalize_transcript_text(audio_meta.title or "未命名视频")
        markdown = "\n\n".join([
            f"# {title}",
            "## 校对文字稿",
            polished_text,
        ]).strip()
        markdown_cache_file.write_text(markdown, encoding="utf-8")
        logger.info(f"GPT 校对文字稿并缓存成功 ({markdown_cache_file})")
        return markdown

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
            write_task_status(
                task_id=task_id,
                output_dir=NOTE_OUTPUT_DIR,
                status=status,
                message=message,
                title=title,
                platform=platform,
            )
        except Exception as e:
            logger.error(f"写入状态文件失败 (task_id={task_id})：{e}")

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
        error_message = getattr(exc, 'detail', str(exc))
        if isinstance(error_message, dict):
            try:
                error_message = json.dumps(error_message, ensure_ascii=False)
            except:
                error_message = str(error_message)
        self._update_status(task_id, TaskStatus.FAILED, message=error_message)

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
        task_id = audio_cache_file.stem.split("_")[0]
        self._update_status(task_id, status_phase)

        # 已有缓存，尝试加载
        if audio_cache_file.exists():
            logger.info(f"检测到音频缓存 ({audio_cache_file})，直接读取")
            try:
                data = json.loads(audio_cache_file.read_text(encoding="utf-8"))
                return AudioDownloadResult(**data)
            except Exception as e:
                logger.warning(f"读取音频缓存失败，将重新下载：{e}")

        # 有字幕且不需要截图/视频理解时，只提取元信息不下载文件
        if skip_download:
            logger.info("已有字幕，仅提取视频元信息（不下载音视频）")
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
                logger.info(f"元信息提取完成 ({audio_cache_file})")
                return audio
            except Exception as exc:
                logger.warning(f"元信息提取失败，将尝试完整下载: {exc}")

        # 判断是否需要下载视频
        need_video = screenshot or video_understanding
        if screenshot and not grid_size:
            grid_size = [2, 2]

        frame_interval = video_interval if video_interval and video_interval > 0 else 6
        if need_video:
            try:
                logger.info("开始下载视频")
                video_path_str = downloader.download_video(video_url)
                self.video_path = Path(video_path_str)
                logger.info(f"视频下载完成：{self.video_path}")

                if grid_size:
                    self.video_img_urls = VideoReader(
                        video_path=str(self.video_path),
                        grid_size=tuple(grid_size),
                        frame_interval=frame_interval,
                        unit_width=960,
                        unit_height=540,
                        save_quality=80,
                    ).run()
                else:
                    logger.info("未指定 grid_size，跳过缩略图生成")
            except Exception as exc:
                logger.error(f"视频下载失败：{exc}")
                self._handle_exception(task_id, exc)
                raise

        # 下载音频
        try:
            logger.info("开始下载音频")
            audio = downloader.download(
                video_url=video_url,
                quality=quality,
                output_dir=output_path,
                need_video=need_video,
            )
            audio_cache_file.write_text(json.dumps(asdict(audio), ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"音频下载并缓存成功 ({audio_cache_file})")
            return audio
        except Exception as exc:
            logger.error(f"音频下载失败：{exc}")
            self._handle_exception(task_id, exc)
            raise


    def _get_transcript(
        self,
        downloader: Downloader,
        video_url: str,
        audio_file: str,
        transcript_cache_file: Path,
        status_phase: TaskStatus,
        task_id: Optional[str] = None,
        allow_audio_transcription: bool = False,
    ) -> TranscriptResult | None:
        """
        优先获取平台字幕，没有则 fallback 到音频转写

        :param downloader: 下载器实例
        :param video_url: 视频链接
        :param audio_file: 音频文件路径（用于 fallback 转写）
        :param transcript_cache_file: 缓存文件路径
        :param status_phase: 状态枚举
        :param task_id: 任务 ID
        :param allow_audio_transcription: 无字幕时是否允许音频转写
        :return: TranscriptResult 对象
        """
        self._update_status(task_id, status_phase)

        # 已有缓存，直接返回
        if transcript_cache_file.exists():
            logger.info(f"检测到转写缓存 ({transcript_cache_file})，尝试读取")
            try:
                transcript = self._load_transcript_cache(
                    transcript_cache_file,
                    allow_audio_transcription=allow_audio_transcription,
                )
                if transcript:
                    return transcript
            except Exception as e:
                logger.warning(f"加载转写缓存失败，将重新获取：{e}")

        # 1. 先尝试获取平台字幕
        logger.info("尝试获取平台字幕...")
        try:
            transcript = downloader.download_subtitles(video_url)
            if transcript and transcript.segments:
                logger.info(f"成功获取平台字幕，共 {len(transcript.segments)} 段")
                # 缓存结果
                transcript_cache_file.write_text(
                    json.dumps(asdict(transcript), ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                return transcript
            else:
                logger.info("平台无可用字幕")
        except Exception as e:
            logger.warning(f"获取平台字幕失败: {e}")

        # 2. Fallback 到音频转写
        if not allow_audio_transcription:
            raise RuntimeError(self.AUDIO_TRANSCRIPTION_CONFIRMATION_MESSAGE)

        return self._transcribe_audio(
            audio_file=audio_file,
            transcript_cache_file=transcript_cache_file,
            status_phase=status_phase,
        )

    def _transcribe_audio(
        self,
        audio_file: str,
        transcript_cache_file: Path,
        status_phase: TaskStatus,
    ) -> TranscriptResult | None:
        """
        1. 检查转写缓存；若存在则尝试加载，否则调用转写器生成并缓存。
        2. 返回 TranscriptResult 对象

        :param audio_file: 音频文件本地路径
        :param transcript_cache_file: 转写结果缓存路径
        :param status_phase: 对应的状态枚举，如 TaskStatus.TRANSCRIBING
        :return: TranscriptResult 对象
        """
        task_id = transcript_cache_file.stem.split("_")[0]
        self._update_status(task_id, status_phase)

        # 已有缓存，尝试加载
        if transcript_cache_file.exists():
            logger.info(f"检测到转写缓存 ({transcript_cache_file})，尝试读取")
            try:
                data = json.loads(transcript_cache_file.read_text(encoding="utf-8"))
                segments = [TranscriptSegment(**seg) for seg in data.get("segments", [])]
                return TranscriptResult(language=data["language"], full_text=data["full_text"], segments=segments)
            except Exception as e:
                logger.warning(f"加载转写缓存失败，将重新转写：{e}")

        # 调用转写器
        try:
            logger.info("开始转写音频")
            transcript = self.transcriber.transcript(file_path=audio_file)
            if isinstance(transcript.raw, dict):
                transcript.raw.setdefault("source", "audio_transcription")
            elif transcript.raw is None:
                transcript.raw = {"source": "audio_transcription"}
            else:
                transcript.raw = {
                    "source": "audio_transcription",
                    "transcriber_raw": str(transcript.raw),
                }
            transcript_cache_file.write_text(json.dumps(asdict(transcript), ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"转写并缓存成功 ({transcript_cache_file})")
            return transcript
        except Exception as exc:
            logger.error(f"音频转写失败：{exc}")
            self._handle_exception(task_id, exc)
            raise

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

        source = GPTSource(
            title=audio_meta.title,
            segment=transcript.segments,
            tags=audio_meta.raw_info.get("tags", []),
            screenshot=screenshot,
            video_img_urls=video_img_urls,
            link=link,
            _format=formats,
            style=style,
            extras=extras,
            checkpoint_key=task_id,
        )

        try:
            markdown = gpt.summarize(source)
            markdown_cache_file.write_text(markdown, encoding="utf-8")
            logger.info(f"GPT 总结并缓存成功 ({markdown_cache_file})")
            return markdown
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
        if "screenshot" in formats and video_path:
            try:
                markdown = self._insert_screenshots(markdown, video_path)
            except Exception as exc:
                logger.warning("截图插入失败，跳过该步骤")

        if "link" in formats:
            try:
                markdown = replace_content_markers(markdown, video_id=audio_meta.video_id, platform=platform)
            except Exception as e:
                logger.warning(f"链接插入失败，跳过该步骤：{e}")

        return markdown

    def _insert_screenshots(self, markdown: str, video_path: Path) -> str | None | Any:
        """
        扫描 Markdown 文本中所有 Screenshot 标记，并替换为实际生成的截图链接。

        :param markdown: 含有 *Screenshot-mm:ss 或 Screenshot-[mm:ss] 标记的 Markdown 文本
        :param video_path: 本地视频文件路径
        :return: 替换后的 Markdown 字符串
        """
        matches: List[Tuple[str, int]] = extract_screenshot_timestamps(markdown)
        for idx, (marker, ts) in enumerate(matches):
            try:
                img_path = generate_screenshot(str(video_path), str(IMAGE_OUTPUT_DIR), ts, idx)
                filename = Path(img_path).name
                # 构建前端可访问的 URL，例如 /static/screenshots/{filename}
                img_url = f"{IMAGE_BASE_URL.rstrip('/')}/{filename}"
                markdown = markdown.replace(marker, f"![]({img_url})", 1)
            except Exception as exc:
                logger.error(f"生成截图失败 (timestamp={ts})：{exc}")
                # self._handle_exception(task_id, exc)
                return None
        return markdown

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
