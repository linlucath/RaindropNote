import json
import tempfile
import unittest
from pathlib import Path

from app.services import batch_processed


class TestBatchProcessed(unittest.TestCase):
    def test_find_existing_task_id_purges_legacy_mode_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            legacy = output_dir / "legacy-task.json"
            legacy.write_text(
                json.dumps({
                    "markdown": "# 标题\n\n## 简体中文文字稿\n\n原始文字",
                    "audio_meta": {"video_id": "BV123"},
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            current = output_dir / "current-task.json"
            current.write_text(
                json.dumps({
                    "markdown": "# 标题\n\n校对文字",
                    "mode": "polished_transcript",
                    "audio_meta": {"video_id": "BV123"},
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            deleted_records: list[str] = []

            task_id = batch_processed.find_existing_task_id(
                "BV123",
                output_dir=output_dir,
                delete_task_record=deleted_records.append,
            )

            self.assertEqual(task_id, "current-task")
            self.assertFalse(legacy.exists())
            self.assertEqual(deleted_records, ["legacy-task"])

    def test_mark_processed_videos_adds_task_id_without_mutating_input(self):
        videos = [
            {"video_id": "BV1", "title": "已处理"},
            {"video_id": "BV2", "title": "未处理"},
        ]

        marked = batch_processed.mark_processed_videos(
            videos,
            existing_task_lookup=lambda video_id, mode=None: {"BV1": "task-1"}.get(video_id),
        )

        self.assertEqual(marked[0]["processed_task_id"], "task-1")
        self.assertNotIn("processed_task_id", marked[1])
        self.assertNotIn("processed_task_id", videos[0])


if __name__ == "__main__":
    unittest.main()
