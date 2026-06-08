import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.services.note import NoteGenerator, logger
from app.services import note_task_results
from app.services.progress_state import read_task_status
from app.services.task_runtime import (
    DEFAULT_VIDEO_RESOLUTION,
    SUPPORTED_GENERATION_MODE,
    SUPPORTED_GENERATION_MODES,
    SUPPORTED_VIDEO_RESOLUTIONS,
    VIDEO_DOWNLOAD_MODE,
    default_note_output_dir,
)
from app.services.task_serial_executor import get_task_executor

NOTE_OUTPUT_DIR = default_note_output_dir()


class NoteTaskValidationError(ValueError):
    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class TaskStatusView:
    ok: bool
    data: dict | None = None
    message: str = ""
    code: int = 0


def default_output_dir() -> Path:
    return Path(NOTE_OUTPUT_DIR)


def normalize_generation_mode(mode: Optional[str]) -> str:
    normalized = (mode or SUPPORTED_GENERATION_MODE).strip() or SUPPORTED_GENERATION_MODE
    if normalized not in SUPPORTED_GENERATION_MODES:
        raise NoteTaskValidationError("不支持的任务模式")
    return normalized


def normalize_video_resolution(resolution: Optional[str]) -> str:
    normalized = (resolution or DEFAULT_VIDEO_RESOLUTION).strip() or DEFAULT_VIDEO_RESOLUTION
    if normalized not in SUPPORTED_VIDEO_RESOLUTIONS:
        raise NoteTaskValidationError("不支持的视频分辨率")
    return normalized


def is_note_result_file(path: Path) -> bool:
    return note_task_results.is_note_result_file(path)


def is_polished_transcript_result(result_content: dict) -> bool:
    return note_task_results.is_polished_transcript_result(result_content)


def delete_task_artifacts(task_id: str, output_dir: Path) -> int:
    deleted_files = 0
    for artifact_path in note_task_results.task_artifact_paths(task_id, output_dir):
        if not artifact_path.exists():
            continue
        artifact_path.unlink()
        deleted_files += 1

    return deleted_files


def purge_legacy_task_result(
    task_id: str,
    output_dir: Path,
    *,
    delete_artifacts: Callable[[str, Path], int] | None = None,
    delete_note_record: Callable[[str], Any] | None = None,
) -> int:
    delete_artifacts = delete_artifacts or delete_task_artifacts
    deleted_files = delete_artifacts(task_id, output_dir)
    if delete_note_record:
        delete_note_record(task_id)
    return deleted_files


def list_saved_tasks(
    *,
    output_dir: Path | None = None,
    delete_artifacts: Callable[[str, Path], int] | None = None,
    delete_note_record: Callable[[str], Any] | None = None,
    log: Any = logger,
) -> list[dict]:
    note_output_dir = output_dir or default_output_dir()
    delete_artifacts = delete_artifacts or delete_task_artifacts
    if not note_output_dir.exists():
        return []

    tasks = []
    for result_path in note_output_dir.glob("*.json"):
        if not is_note_result_file(result_path):
            continue

        task_id = result_path.stem
        try:
            with result_path.open("r", encoding="utf-8") as f:
                result_content = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            log.warning(f"读取笔记结果失败，跳过 {result_path}: {e}")
            continue

        if not is_polished_transcript_result(result_content):
            deleted_files = purge_legacy_task_result(
                task_id,
                note_output_dir,
                delete_artifacts=delete_artifacts,
                delete_note_record=delete_note_record,
            )
            log.info(f"已清理旧模式结果 {task_id} ({deleted_files} 个文件)")
            continue

        status = "SUCCESS"
        message = ""
        status_path = note_task_results.note_status_path(note_output_dir, task_id)
        if status_path.exists():
            try:
                with status_path.open("r", encoding="utf-8") as f:
                    status_content = json.load(f)
                status = status_content.get("status", status)
                message = status_content.get("message", "")
            except (OSError, json.JSONDecodeError) as e:
                log.warning(f"读取任务状态失败，使用默认成功状态 {status_path}: {e}")

        tasks.append({
            "task_id": task_id,
            "status": status,
            "message": message,
            "created_at": result_path.stat().st_mtime,
            "result": result_content,
        })

    return sorted(tasks, key=lambda task: task["created_at"], reverse=True)


def extract_result_audio_meta(result_path: Path, *, log: Any = logger) -> dict:
    try:
        with result_path.open("r", encoding="utf-8") as f:
            result_content = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log.warning(f"读取笔记结果失败，跳过 {result_path}: {e}")
        return {}

    return note_task_results.extract_audio_meta(result_content)


def resolve_task_ids_for_delete(
    *,
    task_id: Optional[str],
    video_id: Optional[str],
    platform: Optional[str],
    output_dir: Path,
    log: Any = logger,
) -> list[str]:
    if task_id:
        return [task_id]

    if not video_id or not platform or not output_dir.exists():
        return []

    matched_task_ids = []
    for result_path in output_dir.glob("*.json"):
        if not is_note_result_file(result_path):
            continue

        audio_meta = extract_result_audio_meta(result_path, log=log)
        if audio_meta.get("video_id") == video_id and audio_meta.get("platform") == platform:
            matched_task_ids.append(result_path.stem)

    return matched_task_ids


def save_note_to_file(
    task_id: str,
    note: Any,
    mode: str = SUPPORTED_GENERATION_MODE,
    *,
    output_dir: Path | None = None,
) -> None:
    note_output_dir = output_dir or default_output_dir()
    note_output_dir.mkdir(parents=True, exist_ok=True)
    payload = note_task_results.build_saved_note_payload(note, mode=mode)
    with note_task_results.note_result_path(note_output_dir, task_id).open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def update_task_markdown(
    task_id: str,
    markdown: str,
    *,
    output_dir: Path | None = None,
) -> dict:
    note_output_dir = output_dir or default_output_dir()
    result_path = note_task_results.note_result_path(note_output_dir, task_id)
    result_content = json.loads(result_path.read_text(encoding="utf-8"))
    result_content = note_task_results.build_edited_markdown_payload(
        result_content,
        markdown,
        mode=SUPPORTED_GENERATION_MODE,
    )

    write_json_atomic(result_path, result_content)
    note_task_results.note_markdown_cache_path(note_output_dir, task_id).write_text(
        markdown,
        encoding="utf-8",
    )
    return result_content


def get_task_status_view(
    task_id: str,
    *,
    output_dir: Path | None = None,
    read_status: Callable[..., dict] | None = None,
) -> TaskStatusView:
    note_output_dir = output_dir or default_output_dir()
    result_path = note_task_results.note_result_path(note_output_dir, task_id)
    read_status = read_status or read_task_status

    status_content = read_status(task_id=task_id, output_dir=note_output_dir)
    if status_content:
        status = status_content.get("status")
        message = status_content.get("message", "")

        if status == TaskStatus.SUCCESS.value:
            if result_path.exists():
                with result_path.open("r", encoding="utf-8") as f:
                    result_content = json.load(f)
                return TaskStatusView(ok=True, data={
                    "status": status,
                    "result": result_content,
                    "message": message,
                    "task_id": task_id,
                })

            return TaskStatusView(ok=True, data={
                "status": TaskStatus.PENDING.value,
                "message": "任务完成，但结果文件未找到",
                "task_id": task_id,
            })

        if status == TaskStatus.FAILED.value:
            return TaskStatusView(ok=False, message=message or "任务失败", code=500)

        return TaskStatusView(ok=True, data={
            "status": status,
            "message": message,
            "task_id": task_id,
        })

    if result_path.exists():
        with result_path.open("r", encoding="utf-8") as f:
            result_content = json.load(f)
        return TaskStatusView(ok=True, data={
            "status": TaskStatus.SUCCESS.value,
            "result": result_content,
            "task_id": task_id,
        })

    return TaskStatusView(ok=False, message="任务不存在或已被清理", code=404)


def run_note_task(
    task_id: str,
    video_url: str,
    platform: str,
    quality: DownloadQuality,
    link: bool = False,
    screenshot: bool = False,
    model_name: str | None = None,
    provider_id: str | None = None,
    _format: list | None = None,
    style: str | None = None,
    extras: str | None = None,
    video_understanding: bool = False,
    video_interval: int = 0,
    grid_size: list | None = None,
    mode: str = SUPPORTED_GENERATION_MODE,
    video_resolution: str | None = None,
    *,
    output_dir: Path | None = None,
    note_generator_factory: Callable[[], Any] | None = None,
    executor_factory: Callable[[str], Any] | None = None,
    save_note: Callable[..., Any] | None = None,
    log: Any = logger,
) -> None:
    mode = normalize_generation_mode(mode)
    video_resolution = normalize_video_resolution(video_resolution)
    note_generator_factory = note_generator_factory or NoteGenerator
    executor_factory = executor_factory or get_task_executor

    if mode != VIDEO_DOWNLOAD_MODE and (not model_name or not provider_id):
        raise NoteTaskValidationError("请选择模型和提供者")

    def _execute_note_task():
        return note_generator_factory().generate(
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
            grid_size=grid_size if grid_size is not None else [],
            mode=mode,
            video_resolution=video_resolution,
        )

    note_output_dir = output_dir or default_output_dir()
    save_note_callback = save_note or (
        lambda save_task_id, note, mode=mode: save_note_to_file(
            save_task_id,
            note,
            mode=mode,
            output_dir=note_output_dir,
        )
    )

    executor = executor_factory(mode)
    log.info(f"任务进入执行队列 (task_id={task_id}, mode={mode})")
    note = executor.run(_execute_note_task)
    log.info(f"Note generated: {task_id}")
    if not note or not note.markdown:
        log.warning(f"任务 {task_id} 执行失败，跳过保存")
        return
    save_note_callback(task_id, note, mode=mode)
