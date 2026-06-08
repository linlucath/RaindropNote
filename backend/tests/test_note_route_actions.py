from pathlib import Path
from contextlib import asynccontextmanager
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.enmus.task_status_enums import TaskStatus
from app.routers import note as note_router
from app.services.note_route_actions import GenerateNoteRoutePayload, generate_note_action


def test_generate_note_action_uses_runtime_injected_dependencies():
    payload = GenerateNoteRoutePayload(
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        platform=None,
        quality="fast",
        task_id="retry-task",
        link=True,
        screenshot=False,
        model_name="demo-model",
        provider_id="demo-provider",
        format=["markdown"],
        style="summary",
        extras="extra",
        video_understanding=True,
        video_interval=5,
        grid_size=[2, 2],
        mode="polished_transcript",
        video_resolution="1080",
    )
    output_dir = Path("/tmp/note-route-actions")
    deleted = []
    status_updates = []
    background_tasks = []

    def delete_task_artifacts(task_id, action_output_dir):
        deleted.append((task_id, action_output_dir))
        return 1

    def update_status(task_id, status):
        status_updates.append((task_id, status))

    def add_background_task(*args):
        background_tasks.append(args)

    def run_note_task():
        raise AssertionError("background task should be scheduled, not executed")

    result = generate_note_action(
        payload,
        output_dir=output_dir,
        resolve_platform=lambda action_payload: "youtube",
        normalize_generation_mode=lambda mode: f"normalized:{mode}",
        delete_task_artifacts=delete_task_artifacts,
        update_status=update_status,
        add_background_task=add_background_task,
        run_note_task=run_note_task,
        new_task_id=lambda: "new-task",
        log=None,
    )

    assert result.ok is True
    assert result.data == {"task_id": "retry-task"}
    assert deleted == [("retry-task", output_dir)]
    assert status_updates == [("retry-task", TaskStatus.PENDING)]
    assert background_tasks == [
        (
            run_note_task,
            "retry-task",
            payload.video_url,
            "youtube",
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
            "normalized:polished_transcript",
            "1080",
        )
    ]


def test_generate_note_endpoint_uses_router_uuid_patch_point():
    @asynccontextmanager
    async def lifespan(_app):
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(note_router.router, prefix="/api")

    with patch("app.routers.note.uuid.uuid4", return_value="task-from-router-uuid"), patch(
        "app.routers.note.NoteGenerator._update_status"
    ), patch("app.routers.note.run_note_task") as run_task:
        client = TestClient(app)
        response = client.post(
            "/api/generate_note",
            json={
                "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "quality": "fast",
                "model_name": "demo-model",
                "provider_id": "demo-provider",
            },
        )

    assert response.status_code == 200
    assert response.json()["data"]["task_id"] == "task-from-router-uuid"
    assert run_task.call_args.args[0] == "task-from-router-uuid"


def test_generate_note_endpoint_rejects_invalid_video_resolution_before_scheduling():
    @asynccontextmanager
    async def lifespan(_app):
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(note_router.router, prefix="/api")

    with patch("app.routers.note.NoteGenerator._update_status") as update_status, patch(
        "app.routers.note.run_note_task"
    ) as run_task:
        client = TestClient(app)
        response = client.post(
            "/api/generate_note",
            json={
                "video_url": "https://www.bilibili.com/video/BV123",
                "quality": "fast",
                "mode": "video_download",
                "video_resolution": "999",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "不支持的视频分辨率"
    update_status.assert_not_called()
    run_task.assert_not_called()


def test_generate_note_action_rejects_transcript_tasks_without_model_and_provider():
    payload = GenerateNoteRoutePayload(
        video_url="https://www.bilibili.com/video/BV123",
        platform=None,
        quality="fast",
        task_id=None,
        link=False,
        screenshot=False,
        model_name=None,
        provider_id=None,
        format=["markdown"],
        style=None,
        extras=None,
        video_understanding=False,
        video_interval=0,
        grid_size=[],
        mode="polished_transcript",
        video_resolution="best",
    )
    status_updates = []
    background_tasks = []

    result = generate_note_action(
        payload,
        output_dir=Path("/tmp/note-route-actions"),
        resolve_platform=lambda action_payload: "bilibili",
        normalize_generation_mode=lambda mode: mode,
        normalize_video_resolution=lambda resolution: resolution or "best",
        delete_task_artifacts=lambda task_id, output_dir: 0,
        update_status=lambda task_id, status: status_updates.append((task_id, status)),
        add_background_task=lambda *args: background_tasks.append(args),
        run_note_task=lambda *args: None,
        new_task_id=lambda: "task-without-model",
        log=None,
    )

    assert result.ok is False
    assert result.code == 400
    assert result.msg == "请选择模型和提供者"
    assert status_updates == []
    assert background_tasks == []
