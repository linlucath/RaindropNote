from pathlib import Path
from typing import Any, Callable, Optional

from app.enmus.note_enums import DownloadQuality
from app.services import batch_runner
from app.services import batch_state
from app.services import note_tasks


def create_batch_payload(
    batch_id: str,
    request,
    *,
    infer_platform: Callable[[str], str],
) -> dict:
    return batch_state.create_batch_payload(
        batch_id=batch_id,
        request=request,
        infer_platform=infer_platform,
    )


def build_run_note_task_payload(
    *,
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
    mode: str = note_tasks.SUPPORTED_GENERATION_MODE,
) -> dict:
    return {
        "task_id": task_id,
        "video_url": video_url,
        "platform": platform,
        "quality": quality,
        "link": link,
        "screenshot": screenshot,
        "model_name": model_name,
        "provider_id": provider_id,
        "_format": _format,
        "style": style,
        "extras": extras,
        "video_understanding": video_understanding,
        "video_interval": video_interval,
        "grid_size": grid_size,
        "mode": mode,
    }


def build_batch_runner_dependencies(
    *,
    output_dir: Callable[[], Path],
    new_task_id: Callable[[], str],
    infer_platform: Callable[[str], str],
    find_existing_task_id: Callable[[str, Optional[str]], Optional[str]],
    update_batch: Callable[..., dict],
    set_batch_item: Callable[..., None],
    is_cancel_requested: Callable[[str], bool],
    finalize_batch_cancel: Callable[..., dict],
    write_task_status: Callable[..., Any],
    read_task_status: Callable[..., dict],
    request_task_cancel: Callable[..., Any],
    run_note_task: Callable[..., Any],
    get_batch: Callable[[str], dict],
) -> batch_runner.BatchRunnerDependencies:
    return batch_runner.BatchRunnerDependencies(
        output_dir=output_dir,
        new_task_id=new_task_id,
        infer_platform=infer_platform,
        find_existing_task_id=find_existing_task_id,
        update_batch=update_batch,
        set_batch_item=set_batch_item,
        is_cancel_requested=is_cancel_requested,
        finalize_batch_cancel=finalize_batch_cancel,
        write_task_status=write_task_status,
        read_task_status=read_task_status,
        request_task_cancel=request_task_cancel,
        run_note_task=run_note_task,
        get_batch=get_batch,
    )
