from fastapi import APIRouter
from pydantic import BaseModel

from app.db.favorite_dao import (
    delete_favorite_by_id,
    get_favorite_by_id,
    get_favorite_by_source_task_id,
    list_favorites,
    upsert_favorite,
)
from app.services.favorite_notes import (
    _load_task_result as _load_task_result_from_service,
    build_favorite_note,
)
from app.services.task_runtime import default_note_output_dir
from app.utils.response import ResponseWrapper as R

router = APIRouter()

NOTE_OUTPUT_DIR = str(default_note_output_dir())


class FavoriteCreateRequest(BaseModel):
    task_id: str


def _load_task_result(task_id: str):
    return _load_task_result_from_service(task_id, NOTE_OUTPUT_DIR)


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
    note = build_favorite_note(result)

    favorite = upsert_favorite(
        source_task_id=data.task_id,
        title=note["title"],
        video_id=note["video_id"],
        platform=note["platform"],
        markdown=note["markdown"],
        transcript=note["transcript"],
        audio_meta=note["audio_meta"],
    )
    return R.success({"favorite": favorite}, msg="收藏成功")


@router.delete("/favorites/{favorite_id}")
def remove_favorite(favorite_id: int):
    deleted = delete_favorite_by_id(favorite_id)
    if not deleted:
        return R.error(msg="收藏不存在", code=404)
    return R.success({"deleted": deleted}, msg="取消收藏成功")
