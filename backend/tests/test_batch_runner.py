import json
import tempfile
import unittest
from pathlib import Path

from app.enmus.task_status_enums import TaskStatus
from app.services import batch_runner


class VideoLike:
    def __init__(self, video_id: str, video_url: str, title: str = "", platform: str | None = None):
        self.video_id = video_id
        self.video_url = video_url
        self.title = title
        self.platform = platform


class RequestLike:
    def __init__(self, videos: list[VideoLike]):
        self.videos = videos
        self.mode = "polished_transcript"
        self.skip_existing = False
        self.concurrency = 1
        self.quality = "fast"
        self.link = False
        self.screenshot = False
        self.model_name = None
        self.provider_id = None
        self.format = []
        self.style = None
        self.extras = None
        self.video_understanding = False
        self.video_interval = 0
        self.grid_size = []


class TestBatchRunner(unittest.TestCase):
    def test_run_batch_stops_launching_new_items_after_cancel_request(self):
        batch_id = "batch-runner"
        videos = [
            VideoLike("BV1", "https://www.bilibili.com/video/BV1", "第一个视频"),
            VideoLike("BV2", "https://www.bilibili.com/video/BV2", "第二个视频"),
        ]
        request = RequestLike(videos)
        state = {
            "batch_id": batch_id,
            "status": "PENDING",
            "cancel_requested": False,
            "current_item_title": None,
            "current_item_index": None,
            "items": [
                {"status": "PENDING", "task_id": None, "message": ""},
                {"status": "PENDING", "task_id": None, "message": ""},
            ],
        }
        calls: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            def update_batch(_batch_id, **updates):
                state.update(updates)
                if updates.get("cancel_requested"):
                    state["cancel_requested"] = True
                return state

            def set_batch_item(_batch_id, index, **updates):
                state["items"][index].update(updates)

            def run_note_task(**kwargs):
                calls.append(kwargs["video_url"])
                (output_dir / f"{kwargs['task_id']}.json").write_text(
                    json.dumps({"ok": True}),
                    encoding="utf-8",
                )
                update_batch(batch_id, status=TaskStatus.CANCELLING.value, cancel_requested=True)

            deps = batch_runner.BatchRunnerDependencies(
                output_dir=lambda: output_dir,
                new_task_id=lambda: f"task-{len(calls) + 1}",
                infer_platform=lambda _url: "bilibili",
                find_existing_task_id=lambda _video_id, _mode=None: None,
                update_batch=update_batch,
                set_batch_item=set_batch_item,
                is_cancel_requested=lambda _batch_id: state["cancel_requested"],
                finalize_batch_cancel=lambda _batch_id: state.update({
                    "status": TaskStatus.CANCELLED.value,
                    "items": [
                        {**state["items"][0]},
                        {**state["items"][1], "status": TaskStatus.CANCELLED.value},
                    ],
                }) or state,
                write_task_status=lambda **_kwargs: None,
                read_task_status=lambda **_kwargs: {},
                request_task_cancel=lambda **_kwargs: None,
                run_note_task=run_note_task,
            )

            batch_runner.run_batch(batch_id, request, deps)

        self.assertEqual(calls, ["https://www.bilibili.com/video/BV1"])
        self.assertEqual(state["status"], TaskStatus.CANCELLED.value)
        self.assertEqual(state["items"][0]["status"], "SUCCESS")
        self.assertEqual(state["items"][1]["status"], TaskStatus.CANCELLED.value)


if __name__ == "__main__":
    unittest.main()
