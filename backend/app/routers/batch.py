import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.services import batch_processed
from app.services import batch_preview as batch_preview_service
from app.services import batch_runner
from app.services import batch_state
from app.services import batch_router_compat
from app.services import batch_task_payloads
from app.services import note_tasks
from app.services.note import NoteGenerator
from app.services.progress_state import read_task_status, request_task_cancel, write_task_status
from app.utils.response import ResponseWrapper as R

router = APIRouter()

NOTE_OUTPUT_DIR = note_tasks.NOTE_OUTPUT_DIR
SUPPORTED_GENERATION_MODE = note_tasks.SUPPORTED_GENERATION_MODE
BATCH_OUTPUT_DIR = batch_state.BATCH_OUTPUT_DIR
_batch_lock = batch_state._batch_lock
_batches = batch_state._batches

# Compatibility exports: existing tests and sibling routers patch/import these names
# from app.routers.batch. The actual implementation now lives in app.services.batch_preview.
requests = batch_preview_service.requests
yt_dlp = batch_preview_service.yt_dlp
BILIBILI_COOKIES_FILE = batch_preview_service.BILIBILI_COOKIES_FILE
_cookie_manager = batch_preview_service._cookie_manager
_uploader_video_service = batch_preview_service._uploader_video_service

normalize_bilibili_entries = batch_preview_service.normalize_bilibili_entries
normalize_youtube_entries = batch_preview_service.normalize_youtube_entries

_ORIGINAL_INFER_PLATFORM = batch_preview_service.infer_platform_from_url
_ORIGINAL_COOKIE_FILE_PATH = batch_preview_service._cookie_file_path
_ORIGINAL_APPLY_BILIBILI_COOKIE = batch_preview_service._apply_bilibili_cookie
_ORIGINAL_EXTRACT_FLAT_PLAYLIST = batch_preview_service._extract_flat_playlist
_ORIGINAL_EXTRACT_VIDEO_METADATA = batch_preview_service._extract_video_metadata
_ORIGINAL_ENRICH_MISSING_TITLES = batch_preview_service._enrich_missing_titles
_ORIGINAL_REQUEST_YOUTUBE_CONTINUATION = batch_preview_service._request_youtube_browse_continuation
_ORIGINAL_PREVIEW_YOUTUBE_POPULAR = batch_preview_service._preview_youtube_popular_channel_page
_ORIGINAL_PREVIEW_YOUTUBE_FALLBACK = batch_preview_service._preview_youtube_fallback_page
_ORIGINAL_PREVIEW_BILIBILI_FLAT = batch_preview_service._preview_bilibili_flat_page
_ORIGINAL_PREVIEW_SPACE = batch_preview_service.preview_bilibili_space
_ORIGINAL_PREVIEW_SPACE_PAGE = batch_preview_service.preview_bilibili_space_page

_normalize_youtube_channel_url = batch_preview_service._normalize_youtube_channel_url
_build_youtube_popular_videos_url = batch_preview_service._build_youtube_popular_videos_url
_build_youtube_uploads_playlist_url = batch_preview_service._build_youtube_uploads_playlist_url
_apply_default_bilibili_space_order = batch_preview_service._apply_default_bilibili_space_order
_parse_bilibili_space_video_request = batch_preview_service._parse_bilibili_space_video_request
_youtube_request_headers = batch_preview_service._youtube_request_headers
_extract_youtube_page_initial_data = batch_preview_service._extract_youtube_page_initial_data
_parse_youtube_view_count = batch_preview_service._parse_youtube_view_count
_extract_youtube_lockup_video = batch_preview_service._extract_youtube_lockup_video
_extract_youtube_videos_from_rich_grid_contents = batch_preview_service._extract_youtube_videos_from_rich_grid_contents
_extract_youtube_rich_grid_continuation_token = batch_preview_service._extract_youtube_rich_grid_continuation_token
_extract_youtube_page_rich_grid = batch_preview_service._extract_youtube_page_rich_grid
_extract_youtube_popular_chip_token = batch_preview_service._extract_youtube_popular_chip_token
_extract_youtube_continuation_rich_grid = batch_preview_service._extract_youtube_continuation_rich_grid
_page_fetch_window = batch_preview_service._page_fetch_window

_BATCH_PREVIEW_PATCH_ALIASES = {"infer_platform_from_url": "_infer_platform_from_url"}


class BatchPreviewRequest(BaseModel):
    space_url: str
    limit: int = Field(default=0, ge=0, le=500)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)


class BatchVideo(BaseModel):
    video_id: str
    video_url: str
    title: str = ""
    platform: Optional[str] = None


class BatchStartRequest(BaseModel):
    videos: list[BatchVideo]
    mode: str = SUPPORTED_GENERATION_MODE
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


class BatchCancelRequest(BaseModel):
    batch_id: str


def _delete_task_artifacts(task_id: str, output_dir: Path) -> int:
    return note_tasks.delete_task_artifacts(task_id, output_dir)


def run_note_task(
    task_id: str,
    video_url: str,
    platform: str,
    quality: DownloadQuality,
    link: bool = False,
    screenshot: bool = False,
    model_name: Optional[str] = None,
    provider_id: Optional[str] = None,
    _format: list | None = None,
    style: Optional[str] = None,
    extras: Optional[str] = None,
    video_understanding: bool = False,
    video_interval: int = 0,
    grid_size: list | None = None,
    mode: str = SUPPORTED_GENERATION_MODE,
) -> None:
    return note_tasks.run_note_task(
        **batch_task_payloads.build_run_note_task_payload(
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
            grid_size=grid_size,
            mode=mode,
        ),
        output_dir=Path(NOTE_OUTPUT_DIR),
        note_generator_factory=NoteGenerator,
    )


def _sync_batch_preview_patchables() -> dict[str, object]:
    return batch_router_compat.sync_router_patchables(
        batch_preview_service,
        globals(),
        batch_router_compat.BATCH_PREVIEW_PATCHABLE_NAMES,
        aliases=_BATCH_PREVIEW_PATCH_ALIASES,
    )


def _patched_batch_preview_service():
    return batch_router_compat.patched_router_patchables(
        batch_preview_service,
        globals(),
        batch_router_compat.BATCH_PREVIEW_PATCHABLE_NAMES,
        aliases=_BATCH_PREVIEW_PATCH_ALIASES,
    )


def _sync_batch_state_patchables() -> dict[str, object]:
    return batch_router_compat.sync_router_patchables(
        batch_state,
        globals(),
        batch_router_compat.BATCH_STATE_PATCHABLE_NAMES,
    )


def _patched_batch_state():
    return batch_router_compat.patched_router_patchables(
        batch_state,
        globals(),
        batch_router_compat.BATCH_STATE_PATCHABLE_NAMES,
    )


def _build_batch_runner_dependencies() -> batch_runner.BatchRunnerDependencies:
    return batch_task_payloads.build_batch_runner_dependencies(
        output_dir=lambda: Path(NOTE_OUTPUT_DIR),
        new_task_id=lambda: str(uuid.uuid4()),
        infer_platform=_infer_platform_from_url,
        find_existing_task_id=find_existing_task_id,
        update_batch=_update_batch,
        set_batch_item=_set_item,
        is_cancel_requested=_is_cancel_requested,
        finalize_batch_cancel=_finalize_batch_cancel,
        write_task_status=write_task_status,
        read_task_status=read_task_status,
        request_task_cancel=request_task_cancel,
        run_note_task=run_note_task,
        get_batch=lambda batch_id: _batches[batch_id],
    )


def _infer_platform_from_url(url: str) -> str:
    return _ORIGINAL_INFER_PLATFORM(url)


def _cookie_file_path() -> Path:
    return _ORIGINAL_COOKIE_FILE_PATH()


def _apply_bilibili_cookie(ydl_opts: dict) -> dict:
    with _patched_batch_preview_service():
        return _ORIGINAL_APPLY_BILIBILI_COOKIE(ydl_opts)


def _extract_flat_playlist(
    space_url: str,
    limit: int = 0,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> dict:
    with _patched_batch_preview_service():
        return _ORIGINAL_EXTRACT_FLAT_PLAYLIST(space_url, limit=limit, start=start, end=end)


def _extract_video_metadata(video_url: str) -> dict:
    with _patched_batch_preview_service():
        return _ORIGINAL_EXTRACT_VIDEO_METADATA(video_url)


def _enrich_missing_titles(videos: list[dict]) -> list[dict]:
    with _patched_batch_preview_service():
        return _ORIGINAL_ENRICH_MISSING_TITLES(videos)


def _request_youtube_browse_continuation(
    *,
    api_key: str,
    client_version: str,
    visitor_data: str,
    context: dict,
    continuation: str,
    referer: str,
) -> dict:
    with _patched_batch_preview_service():
        return _ORIGINAL_REQUEST_YOUTUBE_CONTINUATION(
            api_key=api_key,
            client_version=client_version,
            visitor_data=visitor_data,
            context=context,
            continuation=continuation,
            referer=referer,
        )


def _preview_youtube_popular_channel_page(
    space_url: str,
    page: int,
    page_size: int,
    limit: int,
) -> dict:
    with _patched_batch_preview_service():
        return _ORIGINAL_PREVIEW_YOUTUBE_POPULAR(
            space_url=space_url,
            page=page,
            page_size=page_size,
            limit=limit,
        )


def _preview_youtube_fallback_page(space_url: str, page: int, page_size: int, limit: int) -> dict:
    with _patched_batch_preview_service():
        return _ORIGINAL_PREVIEW_YOUTUBE_FALLBACK(
            space_url,
            page=page,
            page_size=page_size,
            limit=limit,
        )


def _preview_bilibili_flat_page(space_url: str, page: int, page_size: int, limit: int) -> dict:
    with _patched_batch_preview_service():
        return _ORIGINAL_PREVIEW_BILIBILI_FLAT(
            space_url,
            page=page,
            page_size=page_size,
            limit=limit,
        )


def preview_bilibili_space(space_url: str, limit: int = 10) -> list[dict]:
    with _patched_batch_preview_service():
        return _ORIGINAL_PREVIEW_SPACE(space_url, limit=limit)


def preview_bilibili_space_page(
    space_url: str,
    page: int = 1,
    page_size: int = 20,
    limit: int = 0,
) -> dict:
    with _patched_batch_preview_service():
        payload = _ORIGINAL_PREVIEW_SPACE_PAGE(
            space_url,
            page=page,
            page_size=page_size,
            limit=limit,
        )
    return mark_processed_page_items(payload)


def _now_iso() -> str:
    return batch_state.now_iso()


def _default_batch_title(mode: str) -> str:
    return batch_state.default_batch_title(mode)


def _default_source_label(videos: list[BatchVideo]) -> str:
    return batch_state.default_source_label(videos, infer_platform=_infer_platform_from_url)


def create_batch_payload(batch_id: str, request: BatchStartRequest) -> dict:
    return batch_task_payloads.create_batch_payload(
        batch_id=batch_id,
        request=request,
        infer_platform=_infer_platform_from_url,
    )


TERMINAL_BATCH_STATUSES = batch_state.TERMINAL_BATCH_STATUSES
COMPLETED_ITEM_STATUSES = batch_state.COMPLETED_ITEM_STATUSES


def _is_batch_terminal(status: Optional[str]) -> bool:
    return batch_state.is_batch_terminal(status)


def _load_batch(batch_id: str) -> Optional[dict]:
    return batch_state.load_batch(
        batch_id,
        output_dir=BATCH_OUTPUT_DIR,
        batches=_batches,
    )


def mark_processed_videos(videos: list[dict], mode: Optional[str] = None) -> list[dict]:
    return batch_processed.mark_processed_videos(
        videos,
        mode,
        existing_task_lookup=find_existing_task_id,
    )


def mark_processed_page_items(payload: dict, mode: Optional[str] = None) -> dict:
    return batch_processed.mark_processed_page_items(
        payload,
        mode,
        existing_task_lookup=find_existing_task_id,
    )


def _infer_result_mode(result_content: dict | str) -> str:
    return batch_processed.infer_result_mode(result_content)


def find_existing_task_id(video_id: str, mode: Optional[str] = None) -> Optional[str]:
    return batch_processed.find_existing_task_id(
        video_id,
        mode,
        output_dir=Path(NOTE_OUTPUT_DIR),
        delete_artifacts=_delete_task_artifacts,
        delete_task_record=lambda task_id: NoteGenerator.delete_note(task_id=task_id),
    )


def _save_batch(batch: dict) -> None:
    batch_state.save_batch(batch, output_dir=BATCH_OUTPUT_DIR)


def _update_batch(batch_id: str, **updates) -> dict:
    return batch_state.update_batch(
        batch_id,
        output_dir=BATCH_OUTPUT_DIR,
        batches=_batches,
        batch_lock=_batch_lock,
        **updates,
    )


def _set_item(batch_id: str, index: int, **updates) -> None:
    batch_state.set_batch_item(
        batch_id,
        index,
        output_dir=BATCH_OUTPUT_DIR,
        batches=_batches,
        batch_lock=_batch_lock,
        **updates,
    )


def _is_cancel_requested(batch_id: str) -> bool:
    return batch_state.is_cancel_requested(batch_id, batches=_batches)


def _finalize_batch_cancel(batch_id: str, message: str = "批量任务已取消") -> dict:
    return batch_state.finalize_batch_cancel(
        batch_id,
        message=message,
        output_dir=BATCH_OUTPUT_DIR,
        batches=_batches,
        batch_lock=_batch_lock,
    )


def _request_current_child_cancel(batch: dict) -> None:
    batch_runner.request_current_child_cancel(batch, _build_batch_runner_dependencies())


def _sync_child_cancel_status(batch_id: str, index: int) -> bool:
    return batch_runner.sync_child_cancel_status(
        batch_id,
        index,
        _build_batch_runner_dependencies(),
    )


def _run_batch_item(batch_id: str, request: BatchStartRequest, index: int, video: BatchVideo) -> None:
    batch_runner.run_batch_item(
        batch_id,
        request,
        index,
        video,
        _build_batch_runner_dependencies(),
    )


def run_batch(batch_id: str, request: BatchStartRequest) -> None:
    batch_runner.run_batch(batch_id, request, _build_batch_runner_dependencies())


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
    if data.mode != SUPPORTED_GENERATION_MODE:
        return R.error(msg="当前仅支持校对文字稿模式", code=400)
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
