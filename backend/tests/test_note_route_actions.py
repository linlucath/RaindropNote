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
