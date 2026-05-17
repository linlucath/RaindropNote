import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.favorite_dao import (
    delete_favorite_by_id,
    get_favorite_by_id,
    get_favorite_by_source_task_id,
    list_favorites,
    upsert_favorite,
)
from app.utils.response import ResponseWrapper as R

router = APIRouter()

NOTE_OUTPUT_DIR = os.getenv("NOTE_OUTPUT_DIR", "note_results")


class FavoriteCreateRequest(BaseModel):
    task_id: str


def _load_task_result(task_id: str) -> Optional[dict]:
    result_path = Path(NOTE_OUTPUT_DIR) / f"{task_id}.json"
    if not result_path.exists():
        return None
    try:
        return json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@router.get("/favorites")
def get_favorites():
    return R.success({"favorites": list_favorites()})


@router.get("/favorites/{favorite_id}")
def get_favorite_detail(favorite_id: int):
    favorite = get_favorite_by_id(favorite_id)
    if favorite is None:
        return R.error(msg="收藏不存在", code=404)
    return R.success({"favorite": favorite})


@router.get("/favorites/by-task/{task_id}")
def get_favorite_by_task(task_id: str):
    return R.success({"favorite": get_favorite_by_source_task_id(task_id)})


@router.post("/favorites")
def create_favorite(data: FavoriteCreateRequest):
    result = _load_task_result(data.task_id)
    if result is None:
        return R.error(msg="任务结果不存在，无法收藏", code=404)

    audio_meta = result.get("audio_meta") or result.get("audioMeta") or {}
    favorite = upsert_favorite(
        source_task_id=data.task_id,
        title=audio_meta.get("title") or "未命名文字稿",
        video_id=audio_meta.get("video_id"),
        platform=audio_meta.get("platform"),
        markdown=result.get("markdown") or "",
        transcript=result.get("transcript"),
        audio_meta=audio_meta,
    )
    return R.success({"favorite": favorite}, msg="收藏成功")


@router.delete("/favorites/{favorite_id}")
def remove_favorite(favorite_id: int):
    deleted = delete_favorite_by_id(favorite_id)
    if not deleted:
        return R.error(msg="收藏不存在", code=404)
    return R.success({"deleted": deleted}, msg="取消收藏成功")
