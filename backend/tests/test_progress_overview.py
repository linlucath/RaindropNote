import json
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.enmus.task_status_enums import TaskStatus
from app.routers import note as note_router
from app.services.progress_state import write_task_status


class TestProgressOverview(unittest.TestCase):
    def _make_app(self):
        @asynccontextmanager
        async def lifespan(_app):
            yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(note_router.router, prefix="/api")
        return app

    def test_progress_overview_returns_summary_active_and_recent_terminal_groups(self):
        app = self._make_app()

        with tempfile.TemporaryDirectory() as tmp:
            note_dir = Path(tmp) / "notes"
            batch_dir = note_dir / "batches"
            batch_dir.mkdir(parents=True, exist_ok=True)

            write_task_status(
                task_id="task-pending",
                output_dir=note_dir,
                status=TaskStatus.PENDING,
                title="排队任务",
                platform="bilibili",
            )
            write_task_status(
                task_id="task-running",
                output_dir=note_dir,
                status=TaskStatus.TRANSCRIBING,
                title="转写任务",
                platform="youtube",
            )
            write_task_status(
                task_id="task-cancelling",
                output_dir=note_dir,
                status=TaskStatus.CANCELLING,
                title="正在停止任务",
                platform="local",
            )
            write_task_status(
                task_id="task-failed",
                output_dir=note_dir,
                status=TaskStatus.FAILED,
                message="失败原因",
                title="失败任务",
                platform="bilibili",
            )
            write_task_status(
                task_id="task-cancelled",
                output_dir=note_dir,
                status=TaskStatus.CANCELLED,
                message="已取消",
                title="取消任务",
                platform="bilibili",
            )

            (note_dir / "task-success.json").write_text(
                json.dumps(
                    {
                        "markdown": "# 完成",
                        "audio_meta": {"title": "成功任务", "platform": "bilibili", "video_id": "BV123"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            (batch_dir / "batch-running.json").write_text(
                json.dumps(
                    {
                        "batch_id": "batch-running",
                        "title": "运行中批次",
                        "source_label": "Bilibili",
                        "status": "RUNNING",
                        "created_at": "2026-05-07T00:00:00+00:00",
                        "updated_at": "2026-05-07T00:03:00+00:00",
                        "cancel_requested": False,
                        "current_item_title": "第 2 条",
                        "current_item_index": 1,
                        "total": 3,
                        "completed": 1,
                        "items": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (batch_dir / "batch-cancelled.json").write_text(
                json.dumps(
                    {
                        "batch_id": "batch-cancelled",
                        "title": "已取消批次",
                        "source_label": "Bilibili",
                        "status": "CANCELLED",
                        "created_at": "2026-05-07T00:00:00+00:00",
                        "updated_at": "2026-05-07T00:04:00+00:00",
                        "cancel_requested": True,
                        "current_item_title": None,
                        "current_item_index": None,
                        "total": 2,
                        "completed": 1,
                        "items": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch("app.services.progress_query.NOTE_OUTPUT_DIR", note_dir), \
                    patch("app.services.progress_query.BATCH_OUTPUT_DIR", batch_dir):
                client = TestClient(app)
                response = client.get("/api/progress/overview")

            self.assertEqual(response.status_code, 200)
            payload = response.json()["data"]

        self.assertEqual(
            payload["summary"],
            {
                "pending": 1,
                "running": 2,
                "cancelling": 1,
                "success": 1,
                "failed": 1,
                "cancelled": 2,
            },
        )
        self.assertEqual([item["task_id"] for item in payload["tasks"]["active"]], ["task-cancelling", "task-running", "task-pending"])
        self.assertEqual([item["task_id"] for item in payload["tasks"]["recent_terminal"]], ["task-success", "task-cancelled", "task-failed"])
        self.assertEqual([item["batch_id"] for item in payload["batches"]["active"]], ["batch-running"])
        self.assertEqual([item["batch_id"] for item in payload["batches"]["recent_terminal"]], ["batch-cancelled"])

    def test_progress_overview_skips_corrupt_entries_and_ignores_batch_child_skipped_bucket(self):
        app = self._make_app()

        with tempfile.TemporaryDirectory() as tmp:
            note_dir = Path(tmp) / "notes"
            batch_dir = note_dir / "batches"
            batch_dir.mkdir(parents=True, exist_ok=True)

            (note_dir / "broken.status.json").write_text("{bad json", encoding="utf-8")
            (batch_dir / "broken.json").write_text("{bad json", encoding="utf-8")
            (batch_dir / "batch-success.json").write_text(
                json.dumps(
                    {
                        "batch_id": "batch-success",
                        "title": "成功批次",
                        "source_label": "Bilibili",
                        "status": "SUCCESS",
                        "created_at": "2026-05-07T00:00:00+00:00",
                        "updated_at": "2026-05-07T00:05:00+00:00",
                        "cancel_requested": False,
                        "current_item_title": None,
                        "current_item_index": None,
                        "total": 2,
                        "completed": 2,
                        "items": [
                            {"title": "A", "status": "SUCCESS"},
                            {"title": "B", "status": "SKIPPED"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch("app.services.progress_query.NOTE_OUTPUT_DIR", note_dir), \
                    patch("app.services.progress_query.BATCH_OUTPUT_DIR", batch_dir):
                client = TestClient(app)
                response = client.get("/api/progress/overview")

            self.assertEqual(response.status_code, 200)
            payload = response.json()["data"]

        self.assertEqual(payload["summary"]["success"], 1)
        self.assertEqual(payload["summary"]["pending"], 0)
        self.assertEqual(payload["summary"]["running"], 0)
        self.assertEqual(payload["summary"]["cancelled"], 0)
        self.assertEqual([item["batch_id"] for item in payload["batches"]["recent_terminal"]], ["batch-success"])

    def test_progress_overview_ignores_markdown_intermediate_status_files(self):
        app = self._make_app()

        with tempfile.TemporaryDirectory() as tmp:
            note_dir = Path(tmp) / "notes"
            note_dir.mkdir(parents=True, exist_ok=True)

            write_task_status(
                task_id="real-task",
                output_dir=note_dir,
                status=TaskStatus.TRANSCRIBING,
                title="真实任务",
                platform="bilibili",
            )
            write_task_status(
                task_id="real-task_markdown",
                output_dir=note_dir,
                status=TaskStatus.SUMMARIZING,
                title="中间产物",
                platform="bilibili",
            )

            with patch("app.services.progress_query.NOTE_OUTPUT_DIR", note_dir), \
                    patch("app.services.progress_query.BATCH_OUTPUT_DIR", note_dir / "batches"):
                client = TestClient(app)
                response = client.get("/api/progress/overview")

            self.assertEqual(response.status_code, 200)
            payload = response.json()["data"]

        self.assertEqual([item["task_id"] for item in payload["tasks"]["active"]], ["real-task"])


if __name__ == "__main__":
    unittest.main()
