from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from app.enmus.task_status_enums import TaskStatus


@dataclass
class BatchRunnerDependencies:
    output_dir: Callable[[], Path]
    new_task_id: Callable[[], str]
    infer_platform: Callable[[str], str]
    find_existing_task_id: Callable[[str, Optional[str]], Optional[str]]
    update_batch: Callable[..., dict]
    set_batch_item: Callable[..., None]
    is_cancel_requested: Callable[[str], bool]
    finalize_batch_cancel: Callable[..., dict]
    write_task_status: Callable[..., Any]
    read_task_status: Callable[..., dict]
    request_task_cancel: Callable[..., Any]
    run_note_task: Callable[..., Any]
    get_batch: Optional[Callable[[str], dict]] = None


def request_current_child_cancel(batch: dict, deps: BatchRunnerDependencies) -> None:
    for item in batch.get("items") or []:
        if item.get("status") != "RUNNING":
            continue
        task_id = item.get("task_id")
        if task_id:
            deps.request_task_cancel(task_id=task_id, output_dir=deps.output_dir())


def sync_child_cancel_status(batch_id: str, index: int, deps: BatchRunnerDependencies) -> bool:
    if deps.get_batch is None:
        return False
    item = deps.get_batch(batch_id)["items"][index]
    task_id = item.get("task_id")
    if not task_id:
        return False
    task_status = deps.read_task_status(task_id=task_id, output_dir=deps.output_dir())
    if task_status.get("status") != TaskStatus.CANCELLED.value:
        return False
    deps.set_batch_item(
        batch_id,
        index,
        status=TaskStatus.CANCELLED.value,
        message=task_status.get("message", "任务已取消"),
    )
    return True


def run_batch_item(batch_id: str, request, index: int, video, deps: BatchRunnerDependencies) -> None:
    if deps.is_cancel_requested(batch_id):
        return

    deps.update_batch(batch_id, current_item_title=video.title or None, current_item_index=index)
    existing_task_id = (
        deps.find_existing_task_id(video.video_id, request.mode)
        if request.skip_existing
        else None
    )
    if existing_task_id:
        deps.set_batch_item(batch_id, index, status="SKIPPED", task_id=existing_task_id, message="已存在，已跳过")
        return

    task_id = deps.new_task_id()
    deps.set_batch_item(batch_id, index, status="RUNNING", task_id=task_id, message="")
    deps.write_task_status(
        task_id=task_id,
        output_dir=deps.output_dir(),
        status=TaskStatus.PENDING,
        title=video.title,
        platform=video.platform or deps.infer_platform(video.video_url),
    )
    try:
        platform = video.platform or deps.infer_platform(video.video_url)
        deps.run_note_task(
            task_id=task_id,
            video_url=video.video_url,
            platform=platform,
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
        )
        result_path = deps.output_dir() / f"{task_id}.json"
        if result_path.exists():
            deps.set_batch_item(batch_id, index, status="SUCCESS", message="")
        elif sync_child_cancel_status(batch_id, index, deps):
            pass
        else:
            deps.set_batch_item(batch_id, index, status="FAILED", message="任务未生成结果文件")
    except Exception as exc:
        deps.set_batch_item(batch_id, index, status="FAILED", message=str(exc))


def run_batch(batch_id: str, request, deps: BatchRunnerDependencies) -> None:
    if deps.is_cancel_requested(batch_id):
        deps.finalize_batch_cancel(batch_id)
        return

    deps.update_batch(batch_id, status="RUNNING")
    max_workers = max(1, min(request.concurrency, len(request.videos)))

    if max_workers == 1:
        for index, video in enumerate(request.videos):
            if deps.is_cancel_requested(batch_id):
                deps.finalize_batch_cancel(batch_id)
                return
            run_batch_item(batch_id, request, index, video, deps)
    else:
        next_index = 0
        in_flight: dict = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while next_index < len(request.videos) and len(in_flight) < max_workers:
                if deps.is_cancel_requested(batch_id):
                    break
                future = executor.submit(
                    run_batch_item,
                    batch_id,
                    request,
                    next_index,
                    request.videos[next_index],
                    deps,
                )
                in_flight[future] = next_index
                next_index += 1

            while in_flight:
                done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
                for future in done:
                    in_flight.pop(future, None)
                    future.result()

                while next_index < len(request.videos) and len(in_flight) < max_workers:
                    if deps.is_cancel_requested(batch_id):
                        break
                    future = executor.submit(
                        run_batch_item,
                        batch_id,
                        request,
                        next_index,
                        request.videos[next_index],
                        deps,
                    )
                    in_flight[future] = next_index
                    next_index += 1

                if deps.is_cancel_requested(batch_id) and not in_flight:
                    break

    if deps.is_cancel_requested(batch_id):
        deps.finalize_batch_cancel(batch_id)
        return

    deps.update_batch(batch_id, current_item_title=None, current_item_index=None)
