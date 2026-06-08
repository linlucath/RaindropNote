import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.models.notes_model import NoteResult
from app.services import note_task_results
from app.services import note_tasks


class TestNoteTasks(unittest.TestCase):
    def test_note_task_result_helpers_filter_paths_and_build_edit_payload(self):
        self.assertTrue(note_task_results.is_note_result_file(Path("task-1.json")))
        self.assertFalse(note_task_results.is_note_result_file(Path("task-1.status.json")))
        self.assertFalse(note_task_results.is_note_result_file(Path("task-1_audio.json")))
        self.assertFalse(note_task_results.is_note_result_file(Path("task-1_transcript.json")))
        self.assertTrue(
            note_task_results.is_polished_transcript_result({"mode": "polished_transcript"})
        )

        original = {
            "markdown": "旧内容",
            "mode": "legacy",
            "audio_meta": {"video_id": "BV123"},
        }
        edited_at = datetime(2026, 6, 2, tzinfo=timezone.utc)

        result = note_task_results.build_edited_markdown_payload(
            original,
            "新内容",
            edited_at=edited_at,
            mode="polished_transcript",
        )

        self.assertEqual(result["markdown"], "新内容")
        self.assertEqual(result["mode"], "polished_transcript")
        self.assertEqual(result["edited_at"], "2026-06-02T00:00:00+00:00")
        self.assertEqual(result["audio_meta"], {"video_id": "BV123"})
        self.assertEqual(original["markdown"], "旧内容")

    def test_list_saved_tasks_uses_runtime_delete_artifacts_patch_for_legacy_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            legacy_result = output_dir / "task-legacy.json"
            legacy_result.write_text(
                json.dumps({"markdown": "# legacy"}, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch.object(note_tasks, "delete_task_artifacts", return_value=3) as delete_artifacts:
                tasks = note_tasks.list_saved_tasks(output_dir=output_dir)

        self.assertEqual(tasks, [])
        delete_artifacts.assert_called_once_with("task-legacy", output_dir)

    def test_run_note_task_uses_injected_pipeline_dependencies(self):
        fake_note = NoteResult(markdown="# 标题", transcript=None, audio_meta=None)
        generator = Mock()
        generator.generate.return_value = fake_note
        generator_factory = Mock(return_value=generator)
        executor = Mock()
        executor.run.side_effect = lambda fn: fn()
        executor_factory = Mock(return_value=executor)
        save_note = Mock()

        note_tasks.run_note_task(
            task_id="task-1",
            video_url="https://www.bilibili.com/video/BV123",
            platform="bilibili",
            quality=DownloadQuality.fast,
            model_name="demo-model",
            provider_id="demo-provider",
            mode="polished_transcript",
            note_generator_factory=generator_factory,
            executor_factory=executor_factory,
            save_note=save_note,
        )

        executor_factory.assert_called_once_with("polished_transcript")
        executor.run.assert_called_once()
        generator.generate.assert_called_once()
        self.assertEqual(generator.generate.call_args.kwargs["task_id"], "task-1")
        self.assertEqual(generator.generate.call_args.kwargs["grid_size"], [])
        save_note.assert_called_once_with("task-1", fake_note, mode="polished_transcript")

    def test_run_note_task_rejects_missing_model_before_generation(self):
        generator_factory = Mock()

        with self.assertRaises(note_tasks.NoteTaskValidationError) as ctx:
            note_tasks.run_note_task(
                task_id="task-1",
                video_url="https://www.bilibili.com/video/BV123",
                platform="bilibili",
                quality=DownloadQuality.fast,
                provider_id="demo-provider",
                note_generator_factory=generator_factory,
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "请选择模型和提供者")
        generator_factory.assert_not_called()

    def test_update_task_markdown_writes_result_and_markdown_cache_in_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            result_path = output_dir / "task-edit.json"
            result_path.write_text(
                json.dumps(
                    {
                        "markdown": "旧内容",
                        "mode": "polished_transcript",
                        "audio_meta": {"video_id": "BV123"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = note_tasks.update_task_markdown(
                "task-edit",
                "新内容",
                output_dir=output_dir,
            )

            saved_result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(result["markdown"], "新内容")
            self.assertEqual(saved_result["markdown"], "新内容")
            self.assertEqual(saved_result["mode"], "polished_transcript")
            self.assertTrue(saved_result["edited_at"])
            self.assertEqual((output_dir / "task-edit_markdown.md").read_text(encoding="utf-8"), "新内容")

    def test_get_task_status_view_prefers_success_status_file_and_includes_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "task-1.json").write_text(
                json.dumps({"markdown": "# done"}, ensure_ascii=False),
                encoding="utf-8",
            )

            view = note_tasks.get_task_status_view(
                "task-1",
                output_dir=output_dir,
                read_status=lambda **_kwargs: {
                    "status": TaskStatus.SUCCESS.value,
                    "message": "完成",
                },
            )

        self.assertTrue(view.ok)
        self.assertEqual(view.data["status"], TaskStatus.SUCCESS.value)
        self.assertEqual(view.data["message"], "完成")
        self.assertEqual(view.data["task_id"], "task-1")
        self.assertEqual(view.data["result"]["markdown"], "# done")

    def test_get_task_status_view_returns_error_for_failed_status_file(self):
        view = note_tasks.get_task_status_view(
            "task-1",
            output_dir=Path("/does/not/matter"),
            read_status=lambda **_kwargs: {
                "status": TaskStatus.FAILED.value,
                "message": "模型失败",
            },
        )

        self.assertFalse(view.ok)
        self.assertEqual(view.code, 500)
        self.assertEqual(view.message, "模型失败")

    def test_get_task_status_view_falls_back_to_saved_result_without_status_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "task-1.json").write_text(
                json.dumps({"markdown": "# cached"}, ensure_ascii=False),
                encoding="utf-8",
            )

            view = note_tasks.get_task_status_view(
                "task-1",
                output_dir=output_dir,
                read_status=lambda **_kwargs: {},
            )

        self.assertTrue(view.ok)
        self.assertEqual(view.data["status"], TaskStatus.SUCCESS.value)
        self.assertEqual(view.data["task_id"], "task-1")
        self.assertEqual(view.data["result"]["markdown"], "# cached")

    def test_get_task_status_view_returns_error_for_missing_task_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            view = note_tasks.get_task_status_view(
                "missing-task",
                output_dir=Path(tmp),
                read_status=lambda **_kwargs: {},
            )

        self.assertFalse(view.ok)
        self.assertEqual(view.code, 404)
        self.assertEqual(view.message, "任务不存在或已被清理")

    def test_get_task_status_view_uses_runtime_read_task_status_patch_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "task-runtime.json").write_text(
                json.dumps({"markdown": "# runtime"}, ensure_ascii=False),
                encoding="utf-8",
            )

            with unittest.mock.patch(
                "app.services.note_tasks.read_task_status",
                return_value={
                    "status": TaskStatus.SUCCESS.value,
                    "message": "runtime patch",
                },
            ) as read_status:
                view = note_tasks.get_task_status_view("task-runtime", output_dir=output_dir)

        self.assertTrue(view.ok)
        self.assertEqual(view.data["message"], "runtime patch")
        read_status.assert_called_once_with(task_id="task-runtime", output_dir=output_dir)

    def test_run_note_task_uses_runtime_factories_by_default(self):
        fake_note = NoteResult(markdown="# Runtime", transcript=None, audio_meta=None)
        generator = Mock()
        generator.generate.return_value = fake_note
        executor = Mock()
        executor.run.side_effect = lambda fn: fn()
        save_note = Mock()

        with unittest.mock.patch("app.services.note_tasks.NoteGenerator", return_value=generator) as generator_cls, \
                unittest.mock.patch("app.services.note_tasks.get_task_executor", return_value=executor) as executor_factory:
            note_tasks.run_note_task(
                task_id="task-runtime",
                video_url="https://www.bilibili.com/video/BV123",
                platform="bilibili",
                quality=DownloadQuality.fast,
                model_name="demo-model",
                provider_id="demo-provider",
                save_note=save_note,
            )

        generator_cls.assert_called_once_with()
        executor_factory.assert_called_once_with("polished_transcript")
        save_note.assert_called_once_with("task-runtime", fake_note, mode="polished_transcript")


if __name__ == "__main__":
    unittest.main()
