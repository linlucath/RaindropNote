import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

import yt_dlp
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.routers.note import NOTE_OUTPUT_DIR, run_note_task
from app.services.cookie_manager import CookieConfigManager
from app.services.progress_state import read_task_status, request_task_cancel, write_task_status
from app.utils.response import ResponseWrapper as R

router = APIRouter()

BATCH_OUTPUT_DIR = Path(NOTE_OUTPUT_DIR) / "batches"
BATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BILIBILI_COOKIES_FILE = os.getenv("BILIBILI_COOKIES_FILE", "cookies.txt")
_batch_lock = Lock()
_batches: dict[str, dict] = {}
_cookie_manager = CookieConfigManager()


class BatchPreviewRequest(BaseModel):
    space_url: str
    limit: int = Field(default=0, ge=0, le=500)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)


class BatchVideo(BaseModel):
    video_id: str
    video_url: str
    title: str = ""


class BatchStartRequest(BaseModel):
    videos: list[BatchVideo]
    mode: str = "transcript"
    quality: DownloadQuality = DownloadQuality.fast
    skip_existing: bool = True
    concurrency: int = Field(default=1, ge=1, le=2)
    link: bool = False
    screenshot: bool = False
    model_name: Optional[str] = None
    provider_id: Optional[str] = None
    format: list[str] = Field(default_factory=list)
    style: Optional[str] = None
    extras: Optional[str] = None
    video_understanding: bool = False
    video_interval: int = 0
    grid_size: list[int] = Field(default_factory=list)
    allow_audio_transcription: bool = False


class BatchCancelRequest(BaseModel):
    batch_id: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_batch_title(mode: str) -> str:
    if mode == "transcript":
        return "批量文字稿任务"
    if mode == "polished_transcript":
        return "批量校对任务"
    return "批量笔记任务"


def _default_source_label(videos: list[BatchVideo]) -> str:
    if videos:
        return "Bilibili"
    return "未知来源"


def create_batch_payload(batch_id: str, request: BatchStartRequest) -> dict:
    now = _now_iso()
    return {
        "batch_id": batch_id,
        "title": _default_batch_title(request.mode),
        "source_label": _default_source_label(request.videos),
        "status": "PENDING",
        "created_at": now,
        "updated_at": now,
        "cancel_requested": False,
        "current_item_title": None,
        "current_item_index": None,
        "total": len(request.videos),
        "completed": 0,
        "items": [
            {
                "video_id": video.video_id,
                "video_url": video.video_url,
                "title": video.title,
                "status": "PENDING",
                "task_id": None,
                "message": "",
            }
            for video in request.videos
        ],
    }


TERMINAL_BATCH_STATUSES = {"SUCCESS", "FAILED", TaskStatus.CANCELLED.value}
COMPLETED_ITEM_STATUSES = {"SUCCESS", "FAILED", "SKIPPED", TaskStatus.CANCELLED.value}


def _is_batch_terminal(status: Optional[str]) -> bool:
    return status in TERMINAL_BATCH_STATUSES


def _load_batch(batch_id: str) -> Optional[dict]:
    if batch_id in _batches:
        return _batches[batch_id]
    path = BATCH_OUTPUT_DIR / f"{batch_id}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    _batches[batch_id] = payload
    return payload


def normalize_bilibili_entries(entries: list[dict]) -> list[dict]:
    videos = []
    seen = set()
    for entry in entries:
        video_id = entry.get("id") or entry.get("bvid")
        if not video_id or not str(video_id).startswith("BV") or video_id in seen:
            continue
        seen.add(video_id)
        videos.append({
            "video_id": video_id,
            "video_url": entry.get("url") or entry.get("webpage_url") or f"https://www.bilibili.com/video/{video_id}",
            "title": entry.get("title") or "",
        })
    return videos


def _cookie_file_path() -> Path:
    cookies_path = Path(BILIBILI_COOKIES_FILE)
    if cookies_path.is_absolute():
        return cookies_path
    return Path(__file__).parent.parent.parent / BILIBILI_COOKIES_FILE


def _apply_bilibili_cookie(ydl_opts: dict) -> dict:
    cookies_path = _cookie_file_path()
    if cookies_path.exists():
        ydl_opts["cookiefile"] = str(cookies_path)
        return ydl_opts

    cookie = (_cookie_manager.get("bilibili") or "").strip()
    if cookie:
        headers = dict(ydl_opts.get("http_headers") or {})
        headers["Cookie"] = cookie
        ydl_opts["http_headers"] = headers
    return ydl_opts


def _extract_flat_playlist(space_url: str, limit: int = 0, start: Optional[int] = None, end: Optional[int] = None) -> dict:
    ydl_opts = {
        "extract_flat": True,
        "skip_download": True,
        "quiet": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    }
    if start is not None:
        ydl_opts["playliststart"] = start
    if end is not None:
        ydl_opts["playlistend"] = end
    elif limit > 0:
        ydl_opts["playlistend"] = limit
    ydl_opts = _apply_bilibili_cookie(ydl_opts)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(space_url, download=False)


def _extract_video_metadata(video_url: str) -> dict:
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "socket_timeout": 10,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    }
    ydl_opts = _apply_bilibili_cookie(ydl_opts)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(video_url, download=False)


def _enrich_missing_titles(videos: list[dict]) -> list[dict]:
    missing_title_indexes = [index for index, video in enumerate(videos) if not video.get("title")]
    if not missing_title_indexes:
        return videos

    enriched = [dict(video) for video in videos]
    max_workers = min(8, len(missing_title_indexes))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_extract_video_metadata, enriched[index]["video_url"]): index
            for index in missing_title_indexes
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                metadata = future.result()
            except Exception:
                continue
            title = (metadata.get("title") or "").strip()
            if title:
                enriched[index]["title"] = title
    return enriched


def preview_bilibili_space(space_url: str, limit: int = 10) -> list[dict]:
    data = _extract_flat_playlist(space_url, limit)
    videos = normalize_bilibili_entries(data.get("entries") or [])
    limited_videos = videos[:limit] if limit > 0 else videos
    return _enrich_missing_titles(limited_videos)


def preview_bilibili_space_page(
    space_url: str,
    page: int = 1,
    page_size: int = 20,
    limit: int = 0,
) -> dict:
    start = (page - 1) * page_size + 1
    if limit > 0 and start > limit:
        return {
            "items": [],
            "page": page,
            "page_size": page_size,
            "has_more": False,
            "total": limit,
        }

    extra_probe = 1
    if limit > 0:
        remaining = limit - start + 1
        fetch_size = max(min(page_size + extra_probe, remaining), 0)
    else:
        fetch_size = page_size + extra_probe

    if fetch_size <= 0:
        return {
            "items": [],
            "page": page,
            "page_size": page_size,
            "has_more": False,
            "total": limit if limit > 0 else None,
        }

    end = start + fetch_size - 1
    data = _extract_flat_playlist(space_url, start=start, end=end)
    videos = normalize_bilibili_entries(data.get("entries") or [])
    has_more = len(videos) > page_size
    visible_videos = _enrich_missing_titles(videos[:page_size])
    total = limit if limit > 0 else None
    return {
        "items": visible_videos,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
        "total": total,
    }



def _infer_result_mode(markdown: str) -> str:
    if "## 校对文字稿" in markdown:
        return "polished_transcript"
    if "## 简体中文文字稿" in markdown:
        return "transcript"
    return "note"


def find_existing_task_id(video_id: str, mode: Optional[str] = None) -> Optional[str]:
    output_dir = Path(NOTE_OUTPUT_DIR)
    for path in output_dir.glob("*.json"):
        name = path.name
        if name.endswith(".status.json") or path.stem.endswith("_audio") or path.stem.endswith("_transcript"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (data.get("audio_meta") or {}).get("video_id") != video_id:
            continue
        if mode and _infer_result_mode(data.get("markdown") or "") != mode:
            continue
        return path.stem
    return None


def _save_batch(batch: dict) -> None:
    BATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = BATCH_OUTPUT_DIR / f"{batch['batch_id']}.json"
    path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")


def _update_batch(batch_id: str, **updates) -> dict:
    with _batch_lock:
        batch = _batches[batch_id]
        batch.update(updates)
        batch["updated_at"] = _now_iso()
        completed = sum(1 for item in batch["items"] if item["status"] in COMPLETED_ITEM_STATUSES)
        batch["completed"] = completed
        batch["total"] = len(batch["items"])
        if batch.get("cancel_requested") and completed == batch["total"]:
            batch["status"] = TaskStatus.CANCELLED.value
        elif completed == batch["total"] and not _is_batch_terminal(batch.get("status")):
            batch["status"] = "SUCCESS" if all(item["status"] in {"SUCCESS", "SKIPPED"} for item in batch["items"]) else "FAILED"
        _save_batch(batch)
        return batch


def _set_item(batch_id: str, index: int, **updates) -> None:
    with _batch_lock:
        batch = _batches[batch_id]
        batch["items"][index].update(updates)
        batch["updated_at"] = _now_iso()
        completed = sum(1 for item in batch["items"] if item["status"] in COMPLETED_ITEM_STATUSES)
        batch["completed"] = completed
        batch["total"] = len(batch["items"])
        if batch.get("cancel_requested") and completed == batch["total"]:
            batch["status"] = TaskStatus.CANCELLED.value
        _save_batch(batch)


def _is_cancel_requested(batch_id: str) -> bool:
    return bool(_batches[batch_id].get("cancel_requested"))


def _finalize_batch_cancel(batch_id: str, message: str = "批量任务已取消") -> dict:
    with _batch_lock:
        batch = _batches[batch_id]
        for item in batch["items"]:
            if item["status"] == "PENDING":
                item["status"] = TaskStatus.CANCELLED.value
                item["message"] = message
        batch["status"] = TaskStatus.CANCELLED.value
        batch["cancel_requested"] = True
        batch["current_item_title"] = None
        batch["current_item_index"] = None
        batch["updated_at"] = _now_iso()
        batch["completed"] = sum(1 for item in batch["items"] if item["status"] in COMPLETED_ITEM_STATUSES)
        batch["total"] = len(batch["items"])
        _save_batch(batch)
        return batch


def _request_current_child_cancel(batch: dict) -> None:
    current_index = batch.get("current_item_index")
    items = batch.get("items") or []
    if current_index is None or current_index < 0 or current_index >= len(items):
        return
    task_id = items[current_index].get("task_id")
    if task_id:
        request_task_cancel(task_id=task_id, output_dir=Path(NOTE_OUTPUT_DIR))


def _sync_child_cancel_status(batch_id: str, index: int) -> bool:
    item = _batches[batch_id]["items"][index]
    task_id = item.get("task_id")
    if not task_id:
        return False
    task_status = read_task_status(task_id=task_id, output_dir=Path(NOTE_OUTPUT_DIR))
    if task_status.get("status") != TaskStatus.CANCELLED.value:
        return False
    _set_item(
        batch_id,
        index,
        status=TaskStatus.CANCELLED.value,
        message=task_status.get("message", "任务已取消"),
    )
    return True


def run_batch(batch_id: str, request: BatchStartRequest) -> None:
    if _is_cancel_requested(batch_id):
        _finalize_batch_cancel(batch_id)
        return

    _update_batch(batch_id, status="RUNNING")

    for index, video in enumerate(request.videos):
        if _is_cancel_requested(batch_id):
            _finalize_batch_cancel(batch_id)
            return

        _update_batch(batch_id, current_item_title=video.title or None, current_item_index=index)
        existing_task_id = find_existing_task_id(video.video_id, request.mode) if request.skip_existing else None
        if existing_task_id:
            _set_item(batch_id, index, status="SKIPPED", task_id=existing_task_id, message="已存在，已跳过")
            continue

        task_id = str(uuid.uuid4())
        _set_item(batch_id, index, status="RUNNING", task_id=task_id, message="")
        write_task_status(
            task_id=task_id,
            output_dir=Path(NOTE_OUTPUT_DIR),
            status=TaskStatus.PENDING,
            title=video.title,
            platform="bilibili",
        )
        try:
            run_note_task(
                task_id=task_id,
                video_url=video.video_url,
                platform="bilibili",
                quality=request.quality,
                link=request.link,
                screenshot=request.screenshot,
                model_name=request.model_name,
                provider_id=request.provider_id,
                _format=request.format,
                style=request.style,
                extras=request.extras,
                video_understanding=request.video_understanding,
                video_interval=request.video_interval,
                grid_size=request.grid_size,
                mode=request.mode,
                allow_audio_transcription=request.allow_audio_transcription,
            )
            result_path = Path(NOTE_OUTPUT_DIR) / f"{task_id}.json"
            if result_path.exists():
                _set_item(batch_id, index, status="SUCCESS", message="")
            elif _sync_child_cancel_status(batch_id, index):
                pass
            else:
                _set_item(batch_id, index, status="FAILED", message="任务未生成结果文件")
        except Exception as exc:
            _set_item(batch_id, index, status="FAILED", message=str(exc))

    if _is_cancel_requested(batch_id):
        _finalize_batch_cancel(batch_id)
        return

    _update_batch(batch_id, current_item_title=None, current_item_index=None)


@router.post("/batch/preview")
def batch_preview(data: BatchPreviewRequest):
    return R.success(preview_bilibili_space_page(
        data.space_url,
        page=data.page,
        page_size=data.page_size,
        limit=data.limit,
    ))


@router.post("/batch/start")
def batch_start(data: BatchStartRequest, background_tasks: BackgroundTasks):
    batch_id = str(uuid.uuid4())
    batch = create_batch_payload(batch_id=batch_id, request=data)
    with _batch_lock:
        _batches[batch_id] = batch
        _save_batch(batch)
    background_tasks.add_task(run_batch, batch_id, data)
    return R.success({"batch_id": batch_id})


@router.post("/batch/cancel")
def batch_cancel(data: BatchCancelRequest):
    batch = _load_batch(data.batch_id)
    if not batch:
        return R.error(msg="批量任务不存在", code=404)

    if _is_batch_terminal(batch.get("status")) or batch.get("cancel_requested"):
        return R.success(batch)

    updated_batch = _update_batch(
        data.batch_id,
        status=TaskStatus.CANCELLING.value,
        cancel_requested=True,
    )
    _request_current_child_cancel(updated_batch)
    return R.success(updated_batch)


@router.get("/batch/status/{batch_id}")
def batch_status(batch_id: str):
    batch = _load_batch(batch_id)
    if batch:
        return R.success(batch)
    return R.error(msg="批量任务不存在", code=404)
