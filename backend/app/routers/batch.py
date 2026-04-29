import json
import os
import uuid
from pathlib import Path
from threading import Lock
from typing import Optional

import yt_dlp
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.enmus.note_enums import DownloadQuality
from app.routers.note import NOTE_OUTPUT_DIR, run_note_task
from app.utils.response import ResponseWrapper as R

router = APIRouter()

BATCH_OUTPUT_DIR = Path(NOTE_OUTPUT_DIR) / "batches"
BATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BILIBILI_COOKIES_FILE = os.getenv("BILIBILI_COOKIES_FILE", "cookies.txt")
_batch_lock = Lock()
_batches: dict[str, dict] = {}


class BatchPreviewRequest(BaseModel):
    space_url: str
    limit: int = Field(default=10, ge=1, le=100)


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
    model_name: Optional[str] = None
    provider_id: Optional[str] = None


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


def _extract_flat_playlist(space_url: str, limit: int) -> dict:
    ydl_opts = {
        "extract_flat": True,
        "skip_download": True,
        "playlistend": limit,
        "quiet": True,
        "nocheckcertificate": True,
    }
    cookies_path = _cookie_file_path()
    if cookies_path.exists():
        ydl_opts["cookiefile"] = str(cookies_path)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(space_url, download=False)


def preview_bilibili_space(space_url: str, limit: int = 10) -> list[dict]:
    data = _extract_flat_playlist(space_url, limit)
    return normalize_bilibili_entries(data.get("entries") or [])[:limit]


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
        completed = sum(1 for item in batch["items"] if item["status"] in {"SUCCESS", "FAILED", "SKIPPED"})
        batch["completed"] = completed
        batch["total"] = len(batch["items"])
        if completed == batch["total"]:
            batch["status"] = "SUCCESS" if all(item["status"] in {"SUCCESS", "SKIPPED"} for item in batch["items"]) else "FAILED"
        _save_batch(batch)
        return batch


def _set_item(batch_id: str, index: int, **updates) -> None:
    with _batch_lock:
        batch = _batches[batch_id]
        batch["items"][index].update(updates)
        completed = sum(1 for item in batch["items"] if item["status"] in {"SUCCESS", "FAILED", "SKIPPED"})
        batch["completed"] = completed
        batch["total"] = len(batch["items"])
        _save_batch(batch)


def run_batch(batch_id: str, request: BatchStartRequest) -> None:
    _update_batch(batch_id, status="RUNNING")

    for index, video in enumerate(request.videos):
        existing_task_id = find_existing_task_id(video.video_id, request.mode) if request.skip_existing else None
        if existing_task_id:
            _set_item(batch_id, index, status="SKIPPED", task_id=existing_task_id, message="已存在，已跳过")
            continue

        task_id = str(uuid.uuid4())
        _set_item(batch_id, index, status="RUNNING", task_id=task_id, message="")
        try:
            run_note_task(
                task_id=task_id,
                video_url=video.video_url,
                platform="bilibili",
                quality=request.quality,
                model_name=request.model_name,
                provider_id=request.provider_id,
                _format=[],
                mode=request.mode,
            )
            result_path = Path(NOTE_OUTPUT_DIR) / f"{task_id}.json"
            if result_path.exists():
                _set_item(batch_id, index, status="SUCCESS", message="")
            else:
                _set_item(batch_id, index, status="FAILED", message="任务未生成结果文件")
        except Exception as exc:
            _set_item(batch_id, index, status="FAILED", message=str(exc))

    _update_batch(batch_id)


@router.post("/batch/preview")
def batch_preview(data: BatchPreviewRequest):
    videos = preview_bilibili_space(data.space_url, data.limit)
    return R.success({"videos": videos})


@router.post("/batch/start")
def batch_start(data: BatchStartRequest, background_tasks: BackgroundTasks):
    batch_id = str(uuid.uuid4())
    batch = {
        "batch_id": batch_id,
        "status": "PENDING",
        "total": len(data.videos),
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
            for video in data.videos
        ],
    }
    with _batch_lock:
        _batches[batch_id] = batch
        _save_batch(batch)
    background_tasks.add_task(run_batch, batch_id, data)
    return R.success({"batch_id": batch_id})


@router.get("/batch/status/{batch_id}")
def batch_status(batch_id: str):
    if batch_id in _batches:
        return R.success(_batches[batch_id])
    path = BATCH_OUTPUT_DIR / f"{batch_id}.json"
    if path.exists():
        return R.success(json.loads(path.read_text(encoding="utf-8")))
    return R.error(msg="批量任务不存在", code=404)
