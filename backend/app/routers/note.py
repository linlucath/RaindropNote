# app/routers/note.py
import json
import os
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel, field_validator

from app.db.video_task_dao import get_task_by_video
from app.enmus.exception import NoteErrorEnum
from app.enmus.note_enums import DownloadQuality
from app.exceptions.note import NoteError
from app.services.note import NoteGenerator, logger
from app.services.progress_query import build_progress_overview
from app.services.progress_state import read_task_status, request_task_cancel
from app.services.task_serial_executor import get_task_executor
from app.utils.response import ResponseWrapper as R
from app.utils.url_parser import extract_video_id
from app.validators.video_url_validator import is_supported_video_url
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from app.enmus.task_status_enums import TaskStatus

# from app.services.downloader import download_raw_audio
# from app.services.whisperer import transcribe_audio

router = APIRouter()
SUPPORTED_GENERATION_MODE = "polished_transcript"


class RecordRequest(BaseModel):
    task_id: Optional[str] = None
    video_id: Optional[str] = None
    platform: Optional[str] = None


class CancelTaskRequest(BaseModel):
    task_id: str


class VideoRequest(BaseModel):
    video_url: str
    platform: str
    quality: DownloadQuality
    screenshot: Optional[bool] = False
    link: Optional[bool] = False
    model_name: Optional[str] = None
    provider_id: Optional[str] = None
    task_id: Optional[str] = None
    format: Optional[list] = []
    style: str = None
    extras: Optional[str]=None
    video_understanding: Optional[bool] = False
    video_interval: Optional[int] = 0
    grid_size: Optional[list] = []
    mode: Optional[str] = SUPPORTED_GENERATION_MODE
    allow_audio_transcription: Optional[bool] = False

    @field_validator("video_url")
    def validate_supported_url(cls, v):
        url = str(v)
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            # 是网络链接，继续用原有平台校验
            if not is_supported_video_url(url):
                raise NoteError(code=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.code,
                                message=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.message)

        return v


NOTE_OUTPUT_DIR = os.getenv("NOTE_OUTPUT_DIR", "note_results")
UPLOAD_DIR = "uploads"


def _is_note_result_file(path: Path) -> bool:
    name = path.name
    return (
        path.suffix == ".json"
        and not name.endswith(".status.json")
        and not path.stem.endswith("_transcript")
        and not path.stem.endswith("_audio")
    )


def _normalize_generation_mode(mode: Optional[str]) -> str:
    normalized = (mode or SUPPORTED_GENERATION_MODE).strip() or SUPPORTED_GENERATION_MODE
    if normalized != SUPPORTED_GENERATION_MODE:
        raise HTTPException(status_code=400, detail="当前仅支持校对文字稿模式")
    return normalized


def _is_polished_transcript_result(result_content: dict) -> bool:
    markdown = result_content.get("markdown")
    return isinstance(markdown, str) and "## 校对文字稿" in markdown


def _purge_legacy_task_result(task_id: str, output_dir: Path) -> int:
    deleted_files = _delete_task_artifacts(task_id, output_dir)
    NoteGenerator.delete_note(task_id=task_id)
    return deleted_files


def list_saved_tasks():
    output_dir = Path(NOTE_OUTPUT_DIR)
    if not output_dir.exists():
        return []

    tasks = []
    for result_path in output_dir.glob("*.json"):
        if not _is_note_result_file(result_path):
            continue

        task_id = result_path.stem
        try:
            with result_path.open("r", encoding="utf-8") as f:
                result_content = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"读取笔记结果失败，跳过 {result_path}: {e}")
            continue

        if not _is_polished_transcript_result(result_content):
            deleted_files = _purge_legacy_task_result(task_id, output_dir)
            logger.info(f"已清理旧模式结果 {task_id} ({deleted_files} 个文件)")
            continue

        status = TaskStatus.SUCCESS.value
        message = ""
        status_path = output_dir / f"{task_id}.status.json"
        if status_path.exists():
            try:
                with status_path.open("r", encoding="utf-8") as f:
                    status_content = json.load(f)
                status = status_content.get("status", status)
                message = status_content.get("message", "")
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"读取任务状态失败，使用默认成功状态 {status_path}: {e}")

        tasks.append({
            "task_id": task_id,
            "status": status,
            "message": message,
            "created_at": result_path.stat().st_mtime,
            "result": result_content,
        })

    return sorted(tasks, key=lambda task: task["created_at"], reverse=True)


def _extract_result_audio_meta(result_path: Path) -> dict:
    try:
        with result_path.open("r", encoding="utf-8") as f:
            result_content = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"读取笔记结果失败，跳过 {result_path}: {e}")
        return {}

    return result_content.get("audio_meta") or result_content.get("audioMeta") or {}


def _resolve_task_ids_for_delete(data: RecordRequest, output_dir: Path) -> list[str]:
    if data.task_id:
        return [data.task_id]

    if not data.video_id or not data.platform or not output_dir.exists():
        return []

    matched_task_ids = []
    for result_path in output_dir.glob("*.json"):
        if not _is_note_result_file(result_path):
            continue

        audio_meta = _extract_result_audio_meta(result_path)
        if audio_meta.get("video_id") == data.video_id and audio_meta.get("platform") == data.platform:
            matched_task_ids.append(result_path.stem)

    return matched_task_ids


def _delete_task_artifacts(task_id: str, output_dir: Path) -> int:
    deleted_files = 0
    artifact_paths = [
        output_dir / f"{task_id}.json",
        output_dir / f"{task_id}.status.json",
        output_dir / f"{task_id}_audio.json",
        output_dir / f"{task_id}_transcript.json",
        output_dir / f"{task_id}_markdown.md",
    ]

    for artifact_path in artifact_paths:
        if not artifact_path.exists():
            continue
        artifact_path.unlink()
        deleted_files += 1

    return deleted_files


def save_note_to_file(task_id: str, note):
    os.makedirs(NOTE_OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json"), "w", encoding="utf-8") as f:
        json.dump(asdict(note), f, ensure_ascii=False, indent=2)


def run_note_task(task_id: str, video_url: str, platform: str, quality: DownloadQuality,
                  link: bool = False, screenshot: bool = False, model_name: str = None, provider_id: str = None,
                  _format: list = None, style: str = None, extras: str = None, video_understanding: bool = False,
                  video_interval=0, grid_size=[], mode: str = SUPPORTED_GENERATION_MODE, allow_audio_transcription: bool = False
                  ):
    mode = _normalize_generation_mode(mode)

    if not model_name or not provider_id:
        raise HTTPException(status_code=400, detail="请选择模型和提供者")

    def _execute_note_task():
        return NoteGenerator().generate(
            video_url=video_url,
            platform=platform,
            quality=quality,
            task_id=task_id,
            model_name=model_name,
            provider_id=provider_id,
            link=link,
            _format=_format,
            style=style,
            extras=extras,
            screenshot=screenshot,
            video_understanding=video_understanding,
            video_interval=video_interval,
            grid_size=grid_size,
            mode=mode,
            allow_audio_transcription=allow_audio_transcription,
        )

    executor = get_task_executor(mode)
    logger.info(f"任务进入执行队列 (task_id={task_id}, mode={mode})")
    note = executor.run(_execute_note_task)
    logger.info(f"Note generated: {task_id}")
    if not note or not note.markdown:
        logger.warning(f"任务 {task_id} 执行失败，跳过保存")
        return
    save_note_to_file(task_id, note)

@router.post('/delete_task')
def delete_task(data: RecordRequest):
    try:
        output_dir = Path(NOTE_OUTPUT_DIR)
        task_ids = _resolve_task_ids_for_delete(data, output_dir)
        deleted_files = sum(_delete_task_artifacts(task_id, output_dir) for task_id in task_ids)
        deleted_records = NoteGenerator.delete_note(
            video_id=data.video_id,
            platform=data.platform,
            task_id=data.task_id,
        )
        return R.success(
            data={
                'task_ids': task_ids,
                'deleted_files': deleted_files,
                'deleted_records': deleted_records,
            },
            msg='删除成功',
        )
    except Exception as e:
        return R.error(msg=e)


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_location = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_location, "wb+") as f:
        f.write(await file.read())

    # 假设你静态目录挂载了 /uploads
    return R.success({"url": f"/uploads/{file.filename}"})


@router.post("/generate_note")
def generate_note(data: VideoRequest, background_tasks: BackgroundTasks):
    try:

        video_id = extract_video_id(data.video_url, data.platform)
        # if not video_id:
        #     raise HTTPException(status_code=400, detail="无法提取视频 ID")
        # existing = get_task_by_video(video_id, data.platform)
        # if existing:
        #     return R.error(
        #         msg='笔记已生成，请勿重复发起',
        #
        #     )
        if data.task_id:
            # 如果传了task_id，说明是重试！
            task_id = data.task_id
            logger.info(f"重试模式，复用已有 task_id={task_id}")
            deleted_files = _delete_task_artifacts(task_id, Path(NOTE_OUTPUT_DIR))
            if deleted_files:
                logger.info(f"重试前已清理旧任务产物 {deleted_files} 个 (task_id={task_id})")
        else:
            # 正常新建任务
            task_id = str(uuid.uuid4())

        # 统一先写入 PENDING，表示已进入队列等待串行执行
        NoteGenerator._update_status(task_id, TaskStatus.PENDING)

        background_tasks.add_task(run_note_task, task_id, data.video_url, data.platform, data.quality, data.link,
                                  data.screenshot, data.model_name, data.provider_id, data.format, data.style,
                                  data.extras, data.video_understanding, data.video_interval, data.grid_size,
                                  _normalize_generation_mode(data.mode), data.allow_audio_transcription or False)
        return R.success({"task_id": task_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task_status/{task_id}")
def get_task_status(task_id: str):
    result_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json")

    # 优先读状态文件
    status_content = read_task_status(task_id=task_id, output_dir=Path(NOTE_OUTPUT_DIR))
    if status_content:
        status = status_content.get("status")
        message = status_content.get("message", "")

        if status == TaskStatus.SUCCESS.value:
            # 成功状态的话，继续读取最终笔记内容
            if os.path.exists(result_path):
                with open(result_path, "r", encoding="utf-8") as rf:
                    result_content = json.load(rf)
                return R.success({
                    "status": status,
                    "result": result_content,
                    "message": message,
                    "task_id": task_id
                })
            else:
                # 理论上不会出现，保险处理
                return R.success({
                    "status": TaskStatus.PENDING.value,
                    "message": "任务完成，但结果文件未找到",
                    "task_id": task_id
                })

        if status == TaskStatus.FAILED.value:
            return R.error(message or "任务失败", code=500)

        return R.success({
            "status": status,
            "message": message,
            "task_id": task_id
        })

    # 没有状态文件，但有结果
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as f:
            result_content = json.load(f)
        return R.success({
            "status": TaskStatus.SUCCESS.value,
            "result": result_content,
            "task_id": task_id
        })

    # 什么都没有，默认PENDING
    return R.success({
        "status": TaskStatus.PENDING.value,
        "message": "任务排队中",
        "task_id": task_id
    })


@router.post('/cancel_task')
def cancel_task_endpoint(data: CancelTaskRequest):
    payload = request_task_cancel(task_id=data.task_id, output_dir=Path(NOTE_OUTPUT_DIR))
    if not payload:
        return R.error(msg='任务不存在', code=404)

    return R.success({
        'task_id': data.task_id,
        'status': payload.get('status', TaskStatus.CANCELLING.value),
        'message': payload.get('message', ''),
    })


@router.get("/task_list")
def get_task_list():
    return R.success({"tasks": list_saved_tasks()})


@router.get("/progress/overview")
def get_progress_overview():
    return R.success(build_progress_overview())


@router.get("/image_proxy")
async def image_proxy(request: Request, url: str):
    headers = {
        "Referer": "https://www.bilibili.com/",
        "User-Agent": request.headers.get("User-Agent", ""),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)

            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="图片获取失败")

            content_type = resp.headers.get("Content-Type", "image/jpeg")
            return StreamingResponse(
                resp.aiter_bytes(),
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",  #  缓存一天
                    "Content-Type": content_type,
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
