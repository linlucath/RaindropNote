import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.routers import batch


class TestBatchRouter(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
