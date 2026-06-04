import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from app.enmus.task_status_enums import TaskStatus


@dataclass(frozen=True)
class NoteRouteActionResult:
    ok: bool
    data: Any = None
    msg: str = "success"
    code: int = 0

    @classmethod
    def success(cls, data: Any = None, msg: str = "success", code: int = 0):
        return cls(ok=True, data=data, msg=msg, code=code)

    @classmethod
    def error(cls, msg: Any = "error", code: int = 500, data: Any = None):
        return cls(ok=False, data=data, msg=str(msg), code=code)


@dataclass(frozen=True)
class DeleteTaskRoutePayload:
    task_id: Optional[str]
    video_id: Optional[str]
    platform: Optional[str]

    @classmethod
    def from_request(cls, request: Any):
        return cls(
            task_id=request.task_id,
            video_id=request.video_id,
            platform=request.platform,
        )


@dataclass(frozen=True)
class UpdateTaskMarkdownRoutePayload:
    task_id: str
    markdown: str

    @classmethod
    def from_request(cls, request: Any):
        return cls(task_id=request.task_id, markdown=request.markdown)


@dataclass(frozen=True)
class CancelTaskRoutePayload:
    task_id: str

    @classmethod
    def from_request(cls, request: Any):
        return cls(task_id=request.task_id)


@dataclass(frozen=True)
class GenerateNoteRoutePayload:
    video_url: str
    platform: Optional[str]
    quality: Any
    task_id: Optional[str]
    link: bool
    screenshot: bool
    model_name: Optional[str]
    provider_id: Optional[str]
    format: Optional[list]
    style: Optional[str]
    extras: Optional[str]
    video_understanding: bool
    video_interval: int
    grid_size: Optional[list]
    mode: Optional[str]

    @classmethod
    def from_request(cls, request: Any):
        return cls(
            video_url=request.video_url,
            platform=request.platform,
            quality=request.quality,
            task_id=request.task_id,
            link=request.link,
            screenshot=request.screenshot,
            model_name=request.model_name,
            provider_id=request.provider_id,
            format=request.format,
            style=request.style,
            extras=request.extras,
            video_understanding=request.video_understanding,
            video_interval=request.video_interval,
            grid_size=request.grid_size,
            mode=request.mode,
        )


def delete_task_action(
    payload: DeleteTaskRoutePayload,
    *,
    output_dir: Path,
    resolve_task_ids_for_delete: Callable[[DeleteTaskRoutePayload, Path], list[str]],
    delete_task_artifacts: Callable[[str, Path], int],
    delete_note_record: Callable[..., Any],
) -> NoteRouteActionResult:
    try:
        task_ids = resolve_task_ids_for_delete(payload, output_dir)
        deleted_files = sum(delete_task_artifacts(task_id, output_dir) for task_id in task_ids)
        deleted_records = delete_note_record(
            video_id=payload.video_id,
            platform=payload.platform,
            task_id=payload.task_id,
        )
    except Exception as exc:
        return NoteRouteActionResult.error(msg=exc)

    return NoteRouteActionResult.success(
        data={
            "task_ids": task_ids,
            "deleted_files": deleted_files,
            "deleted_records": deleted_records,
        },
        msg="删除成功",
    )


def update_task_markdown_action(
    payload: UpdateTaskMarkdownRoutePayload,
    *,
    output_dir: Path,
    update_task_markdown: Callable[..., dict],
    log: Any,
) -> NoteRouteActionResult:
    result_path = output_dir / f"{payload.task_id}.json"

    if not result_path.exists():
        return NoteRouteActionResult.error(msg="任务结果不存在", code=404)

    markdown = payload.markdown
    if not markdown.strip():
        return NoteRouteActionResult.error(msg="文字稿不能为空", code=400)

    try:
        result_content = update_task_markdown(
            payload.task_id,
            markdown,
            output_dir=output_dir,
        )
    except json.JSONDecodeError as exc:
        log.warning(f"读取笔记结果失败，无法保存编辑 {result_path}: {exc}")
        return NoteRouteActionResult.error(msg="任务结果读取失败", code=500)
    except OSError as exc:
        log.error(f"保存编辑后的文字稿失败 ({result_path}): {exc}")
        return NoteRouteActionResult.error(msg="保存文字稿失败", code=500)

    return NoteRouteActionResult.success(
        data={
            "task_id": payload.task_id,
            "result": result_content,
        },
        msg="保存成功",
    )


def generate_note_action(
    payload: GenerateNoteRoutePayload,
    *,
    output_dir: Path,
    resolve_platform: Callable[[GenerateNoteRoutePayload], str],
    normalize_generation_mode: Callable[[Optional[str]], str],
    delete_task_artifacts: Callable[[str, Path], int],
    update_status: Callable[[str, TaskStatus], Any],
    add_background_task: Callable[..., Any],
    run_note_task: Callable[..., Any],
    new_task_id: Callable[[], str] | None = None,
    log: Any = None,
) -> NoteRouteActionResult:
    platform = resolve_platform(payload)

    if payload.task_id:
        task_id = payload.task_id
        if log:
            log.info(f"重试模式，复用已有 task_id={task_id}")
        deleted_files = delete_task_artifacts(task_id, output_dir)
        if deleted_files and log:
            log.info(f"重试前已清理旧任务产物 {deleted_files} 个 (task_id={task_id})")
    else:
        create_task_id = new_task_id or (lambda: str(uuid.uuid4()))
        task_id = create_task_id()

    update_status(task_id, TaskStatus.PENDING)

    add_background_task(
        run_note_task,
        task_id,
        payload.video_url,
        platform,
        payload.quality,
        payload.link,
        payload.screenshot,
        payload.model_name,
        payload.provider_id,
        payload.format,
        payload.style,
        payload.extras,
        payload.video_understanding,
        payload.video_interval,
        payload.grid_size,
        normalize_generation_mode(payload.mode),
    )
    return NoteRouteActionResult.success({"task_id": task_id})


def get_task_status_action(
    task_id: str,
    *,
    output_dir: Path,
    get_task_status_view: Callable[..., Any],
) -> NoteRouteActionResult:
    view = get_task_status_view(task_id, output_dir=output_dir)
    if not view.ok:
        return NoteRouteActionResult.error(view.message, code=view.code)
    return NoteRouteActionResult.success(view.data)


def cancel_task_action(
    payload: CancelTaskRoutePayload,
    *,
    output_dir: Path,
    request_task_cancel: Callable[..., dict | None],
) -> NoteRouteActionResult:
    cancel_payload = request_task_cancel(task_id=payload.task_id, output_dir=output_dir)
    if not cancel_payload:
        return NoteRouteActionResult.error(msg="任务不存在", code=404)

    return NoteRouteActionResult.success({
        "task_id": payload.task_id,
        "status": cancel_payload.get("status", TaskStatus.CANCELLING.value),
        "message": cancel_payload.get("message", ""),
    })
