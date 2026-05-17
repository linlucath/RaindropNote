import json
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.engine import Base
from app.routers import favorite as favorite_router
from app.routers import note as note_router


class TestFavoriteRouter(unittest.TestCase):
    def _build_app(self) -> FastAPI:
        @asynccontextmanager
        async def lifespan(_app):
            yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(note_router.router, prefix="/api")
        app.include_router(favorite_router.router, prefix="/api")
        return app

    @staticmethod
    def _write_task_result(output_dir: Path, task_id: str) -> None:
        (output_dir / f"{task_id}.json").write_text(
            json.dumps(
                {
                    "markdown": "# 测试视频\n\n## 校对文字稿\n\n这是收藏测试正文。",
                    "transcript": {
                        "full_text": "这是收藏测试正文。",
                        "language": "zh",
                        "raw": {"source": "bilibili_subtitle"},
                        "segments": [
                            {"start": 0, "end": 3, "text": "这是收藏测试正文。"},
                        ],
                    },
                    "audio_meta": {
                        "video_id": "BVfavorite",
                        "platform": "bilibili",
                        "title": "测试视频",
                        "duration": 12,
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_favorite_persists_after_original_task_is_deleted(self):
        app = self._build_app()

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            self._write_task_result(output_dir, "task-1")

            engine = create_engine(
                "sqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            Base.metadata.create_all(bind=engine)

            def override_get_db():
                db = testing_session_local()
                try:
                    yield db
                finally:
                    db.close()

            original_note_output_dir = note_router.NOTE_OUTPUT_DIR
            original_favorite_output_dir = favorite_router.NOTE_OUTPUT_DIR

            try:
                note_router.NOTE_OUTPUT_DIR = str(output_dir)
                favorite_router.NOTE_OUTPUT_DIR = str(output_dir)

                with patch("app.db.favorite_dao.get_db", new=override_get_db), patch(
                    "app.routers.note.NoteGenerator.delete_note", return_value=1
                ):
                    client = TestClient(app)

                    create_response = client.post("/api/favorites", json={"task_id": "task-1"})
                    created_favorite = create_response.json()["data"]["favorite"]

                    delete_response = client.post(
                        "/api/delete_task",
                        json={"task_id": "task-1", "video_id": "BVfavorite", "platform": "bilibili"},
                    )
                    list_response = client.get("/api/favorites")
                    detail_response = client.get(f"/api/favorites/{created_favorite['id']}")
                    by_task_response = client.get("/api/favorites/by-task/task-1")
            finally:
                note_router.NOTE_OUTPUT_DIR = original_note_output_dir
                favorite_router.NOTE_OUTPUT_DIR = original_favorite_output_dir

        self.assertEqual(create_response.status_code, 200)
        self.assertEqual(create_response.json()["code"], 0)
        self.assertEqual(created_favorite["source_task_id"], "task-1")
        self.assertEqual(created_favorite["title"], "测试视频")

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["code"], 0)
        self.assertFalse((output_dir / "task-1.json").exists())

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["code"], 0)
        self.assertEqual(len(list_response.json()["data"]["favorites"]), 1)
        self.assertEqual(list_response.json()["data"]["favorites"][0]["source_task_id"], "task-1")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["code"], 0)
        self.assertEqual(detail_response.json()["data"]["favorite"]["markdown"], created_favorite["markdown"])

        self.assertEqual(by_task_response.status_code, 200)
        self.assertEqual(by_task_response.json()["code"], 0)
        self.assertEqual(by_task_response.json()["data"]["favorite"]["id"], created_favorite["id"])

    def test_delete_favorite_removes_saved_copy(self):
        app = self._build_app()

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            self._write_task_result(output_dir, "task-2")

            engine = create_engine(
                "sqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            Base.metadata.create_all(bind=engine)

            def override_get_db():
                db = testing_session_local()
                try:
                    yield db
                finally:
                    db.close()

            original_favorite_output_dir = favorite_router.NOTE_OUTPUT_DIR

            try:
                favorite_router.NOTE_OUTPUT_DIR = str(output_dir)

                with patch("app.db.favorite_dao.get_db", new=override_get_db):
                    client = TestClient(app)

                    create_response = client.post("/api/favorites", json={"task_id": "task-2"})
                    favorite_id = create_response.json()["data"]["favorite"]["id"]

                    delete_response = client.delete(f"/api/favorites/{favorite_id}")
                    list_response = client.get("/api/favorites")
                    by_task_response = client.get("/api/favorites/by-task/task-2")
            finally:
                favorite_router.NOTE_OUTPUT_DIR = original_favorite_output_dir

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["code"], 0)
        self.assertEqual(list_response.json()["data"]["favorites"], [])
        self.assertIsNone(by_task_response.json()["data"]["favorite"])


if __name__ == "__main__":
    unittest.main()
