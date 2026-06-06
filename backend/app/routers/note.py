import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.services import note_tasks
from app.services.note_assets import fetch_image_proxy, save_uploaded_file
from app.services.note import NoteGenerator, logger
from app.services import note_router_helpers
from app.services import note_route_actions
from app.services.progress_query import build_progress_overview
from app.services.progress_state import request_task_cancel
from app.services.task_runtime import default_note_output_dir
from app.services.task_serial_executor import get_task_executor
from app.utils.path_helper import get_uploads_dir
from app.utils.response import ResponseWrapper as R

router = APIRouter()
SUPPORTED_GENERATION_MODE = note_tasks.SUPPORTED_GENERATION_MODE


class RecordRequest(BaseModel):
    task_id: Optional[str] = None
    video_id: Optional[str] = None
    platform: Optional[str] = None


class CancelTaskRequest(BaseModel):
    task_id: str


class UpdateTaskMarkdownRequest(BaseModel):
    task_id: str
    markdown: str

    @field_validator("task_id")
    def validate_task_id(cls, v):
        task_id = v.strip()
        if not task_id or "/" in task_id or "\\" in task_id:
            raise ValueError("非法任务 ID")
        return task_id


class VideoRequest(BaseModel):
    video_url: str
    platform: Optional[str] = None
    quality: DownloadQuality
    screenshot: bool = False
    link: bool = False
    model_name: Optional[str] = None
    provider_id: Optional[str] = None
    task_id: Optional[str] = None
    format: list[str] = Field(default_factory=list)
    style: Optional[str] = None
    extras: Optional[str] = None
    video_understanding: bool = False
    video_interval: int = 0
    grid_size: list[int] = Field(default_factory=list)
    mode: Optional[str] = SUPPORTED_GENERATION_MODE

    @field_validator("video_url")
    def validate_supported_url(cls, v):
        return note_router_helpers.validate_supported_url(v)


NOTE_OUTPUT_DIR = str(default_note_output_dir())
UPLOAD_DIR = get_uploads_dir()


def _is_note_result_file(path: Path) -> bool:
    return note_tasks.is_note_result_file(path)


def _normalize_generation_mode(mode: Optional[str]) -> str:
    return note_router_helpers.normalize_generation_mode(mode)


def _reject_unsupported_platform() -> None:
    note_router_helpers.reject_unsupported_platform()


def _resolve_request_platform(data: VideoRequest) -> str:
    return note_router_helpers.resolve_request_platform(
        video_url=data.video_url,
        platform=data.platform,
    )


def _is_polished_transcript_result(result_content: dict) -> bool:
    return note_tasks.is_polished_transcript_result(result_content)


def _purge_legacy_task_result(task_id: str, output_dir: Path) -> int:
    deleted_files = _delete_task_artifacts(task_id, output_dir)
    NoteGenerator.delete_note(task_id=task_id)
    return deleted_files


def list_saved_tasks():
    return note_tasks.list_saved_tasks(
        output_dir=Path(NOTE_OUTPUT_DIR),
        delete_artifacts=_delete_task_artifacts,
        delete_note_record=lambda task_id: NoteGenerator.delete_note(task_id=task_id),
    )


def _extract_result_audio_meta(result_path: Path) -> dict:
    return note_tasks.extract_result_audio_meta(result_path)


def _resolve_task_ids_for_delete(data: RecordRequest, output_dir: Path) -> list[str]:
    return note_tasks.resolve_task_ids_for_delete(
        task_id=data.task_id,
        video_id=data.video_id,
        platform=data.platform,
        output_dir=output_dir,
    )


def _delete_task_artifacts(task_id: str, output_dir: Path) -> int:
    return note_tasks.delete_task_artifacts(task_id, output_dir)


def save_note_to_file(task_id: str, note, mode: str = SUPPORTED_GENERATION_MODE):
    note_tasks.save_note_to_file(task_id, note, mode=mode, output_dir=Path(NOTE_OUTPUT_DIR))


def _write_json_atomic(path: Path, payload: dict) -> None:
    note_tasks.write_json_atomic(path, payload)


def _action_response(result: note_route_actions.NoteRouteActionResult):
    if result.ok:
        return R.success(data=result.data, msg=result.msg, code=result.code)
    return R.error(msg=result.msg, code=result.code, data=result.data)


def run_note_task(task_id: str, video_url: str, platform: str, quality: DownloadQuality,
                  link: bool = False, screenshot: bool = False, model_name: str | None = None,
                  provider_id: str | None = None, _format: list[str] | None = None,
                  style: str | None = None, extras: str | None = None, video_understanding: bool = False,
                  video_interval: int = 0, grid_size: list[int] | None = None,
                  mode: str = SUPPORTED_GENERATION_MODE
                  ):
    try:
        return note_tasks.run_note_task(
            task_id=task_id,
            video_url=video_url,
            platform=platform,
            quality=quality,
            link=link,
            screenshot=screenshot,
            model_name=model_name,
            provider_id=provider_id,
            _format=_format,
            style=style,
            extras=extras,
            video_understanding=video_understanding,
            video_interval=video_interval,
            grid_size=grid_size or [],
            mode=mode,
            output_dir=Path(NOTE_OUTPUT_DIR),
            note_generator_factory=NoteGenerator,
            executor_factory=get_task_executor,
            save_note=save_note_to_file,
            log=logger,
        )
    except note_tasks.NoteTaskValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

@router.post('/delete_task')
def delete_task(data: RecordRequest):
    return _action_response(note_route_actions.delete_task_action(
        note_route_actions.DeleteTaskRoutePayload.from_request(data),
        output_dir=Path(NOTE_OUTPUT_DIR),
        resolve_task_ids_for_delete=_resolve_task_ids_for_delete,
        delete_task_artifacts=_delete_task_artifacts,
        delete_note_record=NoteGenerator.delete_note,
    ))


@router.post('/update_task_markdown')
def update_task_markdown(data: UpdateTaskMarkdownRequest):
    return _action_response(note_route_actions.update_task_markdown_action(
        note_route_actions.UpdateTaskMarkdownRoutePayload.from_request(data),
        output_dir=Path(NOTE_OUTPUT_DIR),
        update_task_markdown=note_tasks.update_task_markdown,
        log=logger,
    ))


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    result = await save_uploaded_file(file, upload_dir=UPLOAD_DIR)
    return R.success({"url": result.url})


@router.post("/generate_note")
def generate_note(data: VideoRequest, background_tasks: BackgroundTasks):
    try:
        result = note_route_actions.generate_note_action(
            note_route_actions.GenerateNoteRoutePayload.from_request(data),
            output_dir=Path(NOTE_OUTPUT_DIR),
            resolve_platform=_resolve_request_platform,
            normalize_generation_mode=_normalize_generation_mode,
            delete_task_artifacts=_delete_task_artifacts,
            update_status=NoteGenerator._update_status,
            add_background_task=background_tasks.add_task,
            run_note_task=run_note_task,
            new_task_id=lambda: str(uuid.uuid4()),
            log=logger,
        )
        return _action_response(result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task_status/{task_id}")
def get_task_status(task_id: str):
    return _action_response(note_route_actions.get_task_status_action(
        task_id,
        output_dir=Path(NOTE_OUTPUT_DIR),
        get_task_status_view=note_tasks.get_task_status_view,
    ))


@router.post('/cancel_task')
def cancel_task_endpoint(data: CancelTaskRequest):
    return _action_response(note_route_actions.cancel_task_action(
        note_route_actions.CancelTaskRoutePayload.from_request(data),
        output_dir=Path(NOTE_OUTPUT_DIR),
        request_task_cancel=request_task_cancel,
    ))


@router.get("/task_list")
def get_task_list():
    return R.success({"tasks": list_saved_tasks()})


@router.get("/progress/overview")
def get_progress_overview():
    return R.success(build_progress_overview())


@router.get("/image_proxy")
async def image_proxy(request: Request, url: str):
    result = await fetch_image_proxy(url, user_agent=request.headers.get("User-Agent", ""))
    return StreamingResponse(
        result.body,
        media_type=result.media_type,
        headers=result.headers,
    )
