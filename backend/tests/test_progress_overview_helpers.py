import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.enmus.task_status_enums import TaskStatus
from app.services.progress_state import write_task_status
from app.services.progress_overview import (
    build_summary,
    group_items_by_status,
    load_task_items,
    parse_iso,
    summary_bucket,
)
from app.services.task_runtime import ACTIVE_TASK_STATUSES, TERMINAL_TASK_STATUSES


class TestProgressOverviewHelpers(unittest.TestCase):
    def test_parse_iso_falls_back_to_epoch_and_treats_naive_values_as_utc(self):
        epoch = datetime.fromtimestamp(0, tz=timezone.utc)

        self.assertEqual(parse_iso(None), epoch)
        self.assertEqual(parse_iso("not-a-date"), epoch)

        parsed = parse_iso("2026-05-07T12:34:56")
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.isoformat(), "2026-05-07T12:34:56+00:00")

    def test_summary_bucket_maps_known_statuses_and_running_fallbacks(self):
        self.assertEqual(summary_bucket(TaskStatus.PENDING.value), "pending")
        self.assertEqual(summary_bucket(TaskStatus.CANCELLING.value), "cancelling")
        self.assertEqual(summary_bucket(TaskStatus.SUCCESS.value), "success")
        self.assertEqual(summary_bucket(TaskStatus.FAILED.value), "failed")
        self.assertEqual(summary_bucket(TaskStatus.CANCELLED.value), "cancelled")
        self.assertEqual(summary_bucket(TaskStatus.TRANSCRIBING.value), "running")
        self.assertEqual(summary_bucket("RUNNING"), "running")

        summary = build_summary(
            [
                {"status": TaskStatus.PENDING.value},
                {"status": TaskStatus.DOWNLOADING.value},
                {"status": TaskStatus.SUCCESS.value},
                {"status": TaskStatus.CANCELLED.value},
            ]
        )

        self.assertEqual(
            summary,
            {
                "pending": 1,
                "running": 1,
                "cancelling": 0,
                "success": 1,
                "failed": 0,
                "cancelled": 1,
            },
        )

    def test_group_items_by_status_splits_active_and_terminal_sorted_by_updated_at_desc(self):
        items = [
            {"task_id": "terminal-old", "status": TaskStatus.FAILED.value, "updated_at": "bad-date"},
            {
                "task_id": "active-new",
                "status": TaskStatus.TRANSCRIBING.value,
                "updated_at": "2026-05-07T00:03:00+00:00",
            },
            {
                "task_id": "terminal-new",
                "status": TaskStatus.SUCCESS.value,
                "updated_at": "2026-05-07T00:04:00+00:00",
            },
            {
                "task_id": "active-old",
                "status": TaskStatus.PENDING.value,
                "updated_at": "2026-05-07T00:01:00",
            },
            {"task_id": "ignored", "status": "SKIPPED", "updated_at": "2026-05-07T00:05:00+00:00"},
        ]

        active, terminal = group_items_by_status(
            items,
            active_statuses=ACTIVE_TASK_STATUSES,
            terminal_statuses=TERMINAL_TASK_STATUSES,
        )

        self.assertEqual([item["task_id"] for item in active], ["active-new", "active-old"])
        self.assertEqual([item["task_id"] for item in terminal], ["terminal-new", "terminal-old"])

    def test_pure_summary_helpers_are_available_from_summary_module(self):
        from app.services.progress_summary import (
            build_summary as summary_build_summary,
            group_items_by_status as summary_group_items_by_status,
        )

        self.assertIs(summary_build_summary, build_summary)
        self.assertIs(summary_group_items_by_status, group_items_by_status)

    def test_load_task_items_ignores_markdown_audio_and_transcript_intermediate_files(self):
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
            for suffix in ("_markdown", "_audio", "_transcript"):
                write_task_status(
                    task_id=f"real-task{suffix}",
                    output_dir=note_dir,
                    status=TaskStatus.PENDING,
                    title=f"中间文件 {suffix}",
                    platform="bilibili",
                )
                (note_dir / f"result-only{suffix}.json").write_text(
                    json.dumps({"audio_meta": {"title": f"中间结果 {suffix}"}}, ensure_ascii=False),
                    encoding="utf-8",
                )

            (note_dir / "result-only.json").write_text(
                json.dumps(
                    {
                        "markdown": "# 完成",
                        "audio_meta": {"title": "孤立结果", "platform": "youtube"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            items = load_task_items(
                note_dir,
                stale_cancelling_after_seconds=3600,
                write_status=write_task_status,
            )

        self.assertEqual(sorted(item["task_id"] for item in items), ["real-task", "result-only"])

    def test_load_task_items_normalizes_stale_cancelling_and_preserves_message_logic(self):
        with tempfile.TemporaryDirectory() as tmp:
            note_dir = Path(tmp) / "notes"
            note_dir.mkdir(parents=True, exist_ok=True)
            stale_payloads = {
                "stale-default": "",
                "stale-message": "用户请求停止",
            }
            for task_id, message in stale_payloads.items():
                (note_dir / f"{task_id}.status.json").write_text(
                    json.dumps(
                        {
                            "status": TaskStatus.CANCELLING.value,
                            "message": message,
                            "created_at": "2000-01-01T00:00:00+00:00",
                            "updated_at": "2000-01-01T00:00:00+00:00",
                            "title": task_id,
                            "platform": "bilibili",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            items = load_task_items(
                note_dir,
                stale_cancelling_after_seconds=1,
                write_status=write_task_status,
            )

            statuses = {item["task_id"]: item for item in items}
            default_status = json.loads((note_dir / "stale-default.status.json").read_text(encoding="utf-8"))
            message_status = json.loads((note_dir / "stale-message.status.json").read_text(encoding="utf-8"))

        self.assertEqual(statuses["stale-default"]["status"], TaskStatus.CANCELLED.value)
        self.assertEqual(statuses["stale-message"]["status"], TaskStatus.CANCELLED.value)
        self.assertEqual(default_status["message"], "任务已取消")
        self.assertEqual(message_status["message"], "用户请求停止")

    def test_progress_query_legacy_helper_imports_remain_compatible(self):
        from app.services import progress_query

        expected_helpers = [
            "ACTIVE_TASK_STATUSES",
            "ACTIVE_BATCH_STATUSES",
            "TERMINAL_TASK_STATUSES",
            "TERMINAL_BATCH_STATUSES",
            "_safe_read_json",
            "_parse_iso",
            "_result_file_for_task",
            "_infer_task_title",
            "_infer_task_platform",
            "_build_task_item",
            "_normalize_stale_cancelling_task",
            "_load_tasks",
            "_load_batches",
            "_summary_bucket",
        ]
        missing_helpers = [name for name in expected_helpers if not hasattr(progress_query, name)]
        self.assertEqual(missing_helpers, [])

        epoch = datetime.fromtimestamp(0, tz=timezone.utc)
        self.assertEqual(progress_query._parse_iso("bad-date"), epoch)
        self.assertEqual(progress_query._summary_bucket(TaskStatus.FAILED.value), "failed")

        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            scratch_dir = temp_dir / "scratch"
            note_dir = temp_dir / "notes"
            batch_dir = note_dir / "batches"
            scratch_dir.mkdir(parents=True, exist_ok=True)
            batch_dir.mkdir(parents=True, exist_ok=True)

            good_json_path = scratch_dir / "good.json"
            bad_json_path = scratch_dir / "bad.json"
            good_json_path.write_text(json.dumps({"ok": True}), encoding="utf-8")
            bad_json_path.write_text("{bad json", encoding="utf-8")

            self.assertEqual(progress_query._safe_read_json(good_json_path), {"ok": True})
            self.assertIsNone(progress_query._safe_read_json(bad_json_path))

            result_payload = {"audio_meta": {"title": "结果标题", "platform": "youtube"}}
            self.assertEqual(progress_query._infer_task_title({}, result_payload), "结果标题")
            self.assertEqual(progress_query._infer_task_platform({}, result_payload), "youtube")
            self.assertEqual(
                progress_query._build_task_item(
                    "task-from-status",
                    {
                        "status": TaskStatus.SUCCESS.value,
                        "title": "状态标题",
                        "platform": "bilibili",
                        "created_at": "2026-05-07T00:00:00+00:00",
                        "updated_at": "2026-05-07T00:01:00+00:00",
                    },
                    result_payload,
                ),
                {
                    "id": "task-from-status",
                    "task_id": "task-from-status",
                    "title": "状态标题",
                    "platform": "bilibili",
                    "status": TaskStatus.SUCCESS.value,
                    "message": "",
                    "created_at": "2026-05-07T00:00:00+00:00",
                    "updated_at": "2026-05-07T00:01:00+00:00",
                    "has_result": True,
                },
            )

            write_task_status(
                task_id="task-from-status",
                output_dir=note_dir,
                status=TaskStatus.TRANSCRIBING,
                title="状态任务",
                platform="bilibili",
            )
            (note_dir / "task-from-result.json").write_text(
                json.dumps(
                    {"audio_meta": {"title": "结果任务", "platform": "youtube"}},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (batch_dir / "batch-a.json").write_text(
                json.dumps(
                    {
                        "batch_id": "batch-a",
                        "status": "RUNNING",
                        "updated_at": "2026-05-07T00:02:00+00:00",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch("app.services.progress_query.NOTE_OUTPUT_DIR", note_dir), patch(
                "app.services.progress_query.BATCH_OUTPUT_DIR", batch_dir
            ):
                self.assertEqual(
                    progress_query._result_file_for_task("task-from-result"),
                    note_dir / "task-from-result.json",
                )
                self.assertEqual(
                    sorted(item["task_id"] for item in progress_query._load_tasks()),
                    ["task-from-result", "task-from-status"],
                )
                self.assertEqual(
                    [item["batch_id"] for item in progress_query._load_batches()],
                    ["batch-a"],
                )


if __name__ == "__main__":
    unittest.main()
