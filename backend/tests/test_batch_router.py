import json
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.enmus.task_status_enums import TaskStatus
from app.routers import batch


class TestBatchRouter(unittest.TestCase):
    def test_task_status_description_includes_cancelling_and_cancelled(self):
        self.assertEqual(TaskStatus.description(TaskStatus.CANCELLING), "正在停止")
        self.assertEqual(TaskStatus.description(TaskStatus.CANCELLED), "已取消")

    def test_task_status_description_matches_progress_page_copy(self):
        self.assertEqual(TaskStatus.description(TaskStatus.TRANSCRIBING), "转写中")
        self.assertEqual(TaskStatus.description(TaskStatus.SUCCESS), "已完成")

    def test_normalizes_flat_playlist_entries(self):
        videos = batch.normalize_bilibili_entries([
            {"id": "BV123", "url": "https://www.bilibili.com/video/BV123"},
            {"id": "BV456"},
            {"id": None, "url": "https://example.com"},
        ])

        self.assertEqual(videos, [
            {
                "video_id": "BV123",
                "video_url": "https://www.bilibili.com/video/BV123",
                "title": "",
            },
            {
                "video_id": "BV456",
                "video_url": "https://www.bilibili.com/video/BV456",
                "title": "",
            },
        ])

    def test_preview_limits_videos(self):
        with patch("app.routers.batch._extract_flat_playlist", return_value={
            "entries": [
                {"id": "BV1"},
                {"id": "BV2"},
                {"id": "BV3"},
            ]
        }):
            videos = batch.preview_bilibili_space("https://space.bilibili.com/1/upload/video", limit=2)

        self.assertEqual([v["video_id"] for v in videos], ["BV1", "BV2"])

    def test_preview_enriches_missing_titles_from_video_metadata(self):
        with patch("app.routers.batch._extract_flat_playlist", return_value={
            "entries": [
                {"id": "BV1", "url": "https://www.bilibili.com/video/BV1"},
                {"id": "BV2", "title": "已有标题"},
            ]
        }), patch("app.routers.batch._extract_video_metadata", return_value={"title": "补全标题"}) as extract_video:
            videos = batch.preview_bilibili_space("https://space.bilibili.com/1/upload/video", limit=2)

        self.assertEqual(videos[0]["title"], "补全标题")
        self.assertEqual(videos[1]["title"], "已有标题")
        extract_video.assert_called_once_with("https://www.bilibili.com/video/BV1")

    def test_enrich_missing_titles_retries_failed_metadata_lookup(self):
        videos = [
            {"video_id": "BV1", "video_url": "https://www.bilibili.com/video/BV1", "title": ""},
        ]

        with patch(
            "app.routers.batch._extract_video_metadata",
            side_effect=[TimeoutError("timeout"), {"title": "补回标题"}],
        ) as extract_video:
            enriched = batch._enrich_missing_titles(videos)

        self.assertEqual(enriched[0]["title"], "补回标题")
        self.assertEqual(extract_video.call_count, 2)

    def test_preview_page_returns_has_more_when_next_page_exists(self):
        with patch("app.routers.batch._extract_flat_playlist", return_value={
            "entries": [
                {"id": "BV1", "title": "视频1"},
                {"id": "BV2", "title": "视频2"},
                {"id": "BV3", "title": "视频3"},
            ]
        }) as extract_playlist:
            payload = batch.preview_bilibili_space_page(
                "https://space.bilibili.com/1/upload/video",
                page=1,
                page_size=2,
                limit=0,
            )

        self.assertEqual([v["video_id"] for v in payload["items"]], ["BV1", "BV2"])
        self.assertTrue(payload["has_more"])
        extract_playlist.assert_called_once_with(
            "https://space.bilibili.com/1/upload/video",
            start=1,
            end=3,
        )

    def test_preview_page_respects_limit_and_stops_loading_more(self):
        with patch("app.routers.batch._extract_flat_playlist", return_value={
            "entries": [
                {"id": "BV41", "title": "视频41"},
                {"id": "BV42", "title": "视频42"},
                {"id": "BV43", "title": "视频43"},
            ]
        }) as extract_playlist:
            payload = batch.preview_bilibili_space_page(
                "https://space.bilibili.com/1/upload/video",
                page=3,
                page_size=20,
                limit=42,
            )

        self.assertEqual([v["video_id"] for v in payload["items"]], ["BV41", "BV42"])
        self.assertFalse(payload["has_more"])
        extract_playlist.assert_called_once_with(
            "https://space.bilibili.com/1/upload/video",
            start=41,
            end=42,
        )

    def test_extract_flat_playlist_omits_playlistend_when_limit_is_zero(self):
        captured_options = {}

        class FakeYoutubeDL:
            def __init__(self, opts):
                captured_options.update(opts)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, space_url, download=False):
                return {"entries": []}

        with patch("app.routers.batch.yt_dlp.YoutubeDL", FakeYoutubeDL):
            batch._extract_flat_playlist("https://space.bilibili.com/1/upload/video", limit=0)

        self.assertNotIn("playlistend", captured_options)

    def test_find_existing_task_by_video_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "task-1.json"
            result.write_text(
                json.dumps({"audio_meta": {"video_id": "BV123"}}),
                encoding="utf-8",
            )

            with patch("app.routers.batch.NOTE_OUTPUT_DIR", Path(tmp)):
                self.assertEqual(batch.find_existing_task_id("BV123"), "task-1")
                self.assertIsNone(batch.find_existing_task_id("BV999"))

    def test_find_existing_task_matches_requested_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw_transcript = Path(tmp) / "raw-transcript.json"
            raw_transcript.write_text(
                json.dumps({
                    "markdown": "# 标题\n\n## 简体中文文字稿\n\n原始文字",
                    "audio_meta": {"video_id": "BV123"},
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            polished_transcript = Path(tmp) / "polished-transcript.json"
            polished_transcript.write_text(
                json.dumps({
                    "markdown": "# 标题\n\n## 校对文字稿\n\n校对文字",
                    "audio_meta": {"video_id": "BV123"},
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch("app.routers.batch.NOTE_OUTPUT_DIR", Path(tmp)):
                self.assertEqual(batch.find_existing_task_id("BV123", "transcript"), "raw-transcript")
                self.assertEqual(batch.find_existing_task_id("BV123", "polished_transcript"), "polished-transcript")
                self.assertIsNone(batch.find_existing_task_id("BV123", "note"))

    def test_batch_start_request_defaults_match_single_task_defaults(self):
        request = batch.BatchStartRequest(videos=[
            batch.BatchVideo(
                video_id="BV123",
                video_url="https://www.bilibili.com/video/BV123",
                title="示例视频",
            )
        ])

        self.assertFalse(request.link)
        self.assertFalse(request.screenshot)
        self.assertEqual(request.format, [])
        self.assertIsNone(request.style)
        self.assertIsNone(request.extras)
        self.assertFalse(request.video_understanding)
        self.assertEqual(request.video_interval, 0)
        self.assertEqual(request.grid_size, [])
        self.assertFalse(request.allow_audio_transcription)

    def test_new_batch_payload_contains_progress_metadata(self):
        @asynccontextmanager
        async def lifespan(_app):
            yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(batch.router, prefix="/api")

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict("app.routers.batch._batches", clear=True), \
                patch("app.routers.batch.BATCH_OUTPUT_DIR", Path(tmp)), \
                patch("app.routers.batch.uuid.uuid4", return_value="batch-123"), \
                patch("app.routers.batch.run_batch"):
            client = TestClient(app)
            response = client.post("/api/batch/start", json={
                "videos": [
                    {
                        "video_id": "BV123",
                        "video_url": "https://www.bilibili.com/video/BV123",
                        "title": "示例视频",
                    }
                ],
                "mode": "transcript",
            })

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["batch_id"], "batch-123")

            batch_file = Path(tmp) / "batch-123.json"
            self.assertTrue(batch_file.exists())
            payload = json.loads(batch_file.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "PENDING")
        self.assertEqual(payload["title"], "批量文字稿任务")
        self.assertEqual(payload["source_label"], "Bilibili")
        self.assertFalse(payload["cancel_requested"])
        self.assertIsNone(payload["current_item_title"])
        self.assertIsNone(payload["current_item_index"])
        self.assertIsInstance(payload["created_at"], str)
        self.assertEqual(payload["created_at"], payload["updated_at"])

    def test_run_batch_passes_single_task_options_through(self):
        request = batch.BatchStartRequest(
            videos=[
                batch.BatchVideo(
                    video_id="BV123",
                    video_url="https://www.bilibili.com/video/BV123",
                    title="示例视频",
                )
            ],
            mode="polished_transcript",
            quality=batch.DownloadQuality.fast,
            skip_existing=False,
            concurrency=1,
            link=True,
            screenshot=True,
            model_name="deepseek-chat",
            provider_id="provider-1",
            format=["toc", "summary"],
            style="minimal",
            extras="保留关键时间点",
            video_understanding=True,
            video_interval=8,
            grid_size=[3, 2],
            allow_audio_transcription=True,
        )
        batch_id = "batch-1"

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict("app.routers.batch._batches", {
                    batch_id: {
                        "batch_id": batch_id,
                        "status": "PENDING",
                        "total": 1,
                        "completed": 0,
                        "items": [{
                            "video_id": "BV123",
                            "video_url": "https://www.bilibili.com/video/BV123",
                            "title": "示例视频",
                            "status": "PENDING",
                            "task_id": None,
                            "message": "",
                        }],
                    }
                }, clear=True), \
                patch("app.routers.batch.BATCH_OUTPUT_DIR", Path(tmp)), \
                patch("app.routers.batch.NOTE_OUTPUT_DIR", Path(tmp)), \
                patch("app.routers.batch.uuid.uuid4", return_value="task-123"), \
                patch("app.routers.batch.run_note_task") as run_note_task:
            run_note_task.side_effect = lambda **kwargs: (Path(tmp) / f"{kwargs['task_id']}.json").write_text(
                json.dumps({"ok": True}),
                encoding="utf-8",
            )

            batch.run_batch(batch_id, request)

        run_note_task.assert_called_once_with(
            task_id="task-123",
            video_url="https://www.bilibili.com/video/BV123",
            platform="bilibili",
            quality=batch.DownloadQuality.fast,
            link=True,
            screenshot=True,
            model_name="deepseek-chat",
            provider_id="provider-1",
            _format=["toc", "summary"],
            style="minimal",
            extras="保留关键时间点",
            video_understanding=True,
            video_interval=8,
            grid_size=[3, 2],
            mode="polished_transcript",
            allow_audio_transcription=True,
        )


if __name__ == "__main__":
    unittest.main()
