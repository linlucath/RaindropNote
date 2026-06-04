import json
import tempfile
import unittest
from pathlib import Path

from app.enmus.task_status_enums import TaskStatus
from app.services import batch_state


class VideoLike:
    def __init__(self, video_id: str, video_url: str, title: str = "", platform: str | None = None):
        self.video_id = video_id
        self.video_url = video_url
        self.title = title
        self.platform = platform


class BatchRequestLike:
    def __init__(self, videos: list[VideoLike], mode: str = "polished_transcript"):
        self.videos = videos
        self.mode = mode


class TestBatchState(unittest.TestCase):
    def setUp(self):
        self._original_output_dir = batch_state.BATCH_OUTPUT_DIR
        self._original_batches = dict(batch_state._batches)

    def tearDown(self):
        batch_state.BATCH_OUTPUT_DIR = self._original_output_dir
        batch_state._batches.clear()
        batch_state._batches.update(self._original_batches)

    def test_create_batch_payload_preserves_router_contract(self):
        request = BatchRequestLike([
            VideoLike(
                video_id="yt-1",
                video_url="https://www.youtube.com/watch?v=yt-1",
                title="示例 YouTube 视频",
            )
        ])

        payload = batch_state.create_batch_payload("batch-1", request)

        self.assertEqual(payload["batch_id"], "batch-1")
        self.assertEqual(payload["title"], "批量文字稿任务")
        self.assertEqual(payload["source_label"], "YouTube")
        self.assertEqual(payload["status"], "PENDING")
        self.assertEqual(payload["completed"], 0)
        self.assertEqual(payload["total"], 1)
        self.assertFalse(payload["cancel_requested"])
        self.assertIsNone(payload["current_item_title"])
        self.assertIsNone(payload["current_item_index"])
        self.assertEqual(payload["items"][0]["platform"], "youtube")

    def test_update_batch_persists_completed_and_terminal_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch_state.BATCH_OUTPUT_DIR = Path(tmp)
            batch_state._batches.clear()
            batch_state._batches["batch-1"] = {
                "batch_id": "batch-1",
                "status": "RUNNING",
                "total": 2,
                "completed": 0,
                "items": [
                    {"status": "SUCCESS"},
                    {"status": "SKIPPED"},
                ],
            }

            updated = batch_state.update_batch("batch-1")

            self.assertEqual(updated["status"], "SUCCESS")
            self.assertEqual(updated["completed"], 2)
            saved = json.loads((Path(tmp) / "batch-1.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["status"], "SUCCESS")

    def test_finalize_batch_cancel_marks_pending_items_cancelled(self):
        with tempfile.TemporaryDirectory() as tmp:
            batch_state.BATCH_OUTPUT_DIR = Path(tmp)
            batch_state._batches.clear()
            batch_state._batches["batch-2"] = {
                "batch_id": "batch-2",
                "status": "CANCELLING",
                "cancel_requested": True,
                "current_item_title": "当前视频",
                "current_item_index": 0,
                "total": 2,
                "completed": 0,
                "items": [
                    {"status": "SUCCESS", "message": ""},
                    {"status": "PENDING", "message": ""},
                ],
            }

            updated = batch_state.finalize_batch_cancel("batch-2")

            self.assertEqual(updated["status"], TaskStatus.CANCELLED.value)
            self.assertIsNone(updated["current_item_title"])
            self.assertIsNone(updated["current_item_index"])
            self.assertEqual(updated["completed"], 2)
            self.assertEqual(updated["items"][1]["status"], TaskStatus.CANCELLED.value)

    def test_batch_status_helpers_compute_counts_and_terminal_status(self):
        from app.services import batch_status

        batch = {
            "status": "RUNNING",
            "cancel_requested": False,
            "items": [
                {"status": "SUCCESS"},
                {"status": "SKIPPED"},
            ],
        }

        self.assertEqual(batch_status.count_updates(batch), {"completed": 2, "total": 2})
        self.assertEqual(batch_status.next_status(batch | {"completed": 2, "total": 2}), "SUCCESS")


if __name__ == "__main__":
    unittest.main()
