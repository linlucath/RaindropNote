import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.enmus.task_status_enums import TaskStatus
from app.services.note_task_lifecycle import (
    TaskCancelledError,
    cancel_if_requested,
    handle_task_exception,
    update_task_status,
)
from app.services.progress_state import request_task_cancel, write_task_status


class TestNoteTaskLifecycle(unittest.TestCase):
    def test_update_task_status_writes_normalized_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            update_task_status(
                task_id="task-1",
                output_dir=output_dir,
                status=TaskStatus.PARSING,
                message="解析中",
                title="标题",
                platform="bilibili",
                log=Mock(),
            )

            payload = json.loads((output_dir / "task-1.status.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], TaskStatus.PARSING.value)
        self.assertEqual(payload["message"], "解析中")
        self.assertEqual(payload["title"], "标题")
        self.assertEqual(payload["platform"], "bilibili")

    def test_update_task_status_ignores_missing_task_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            update_task_status(
                task_id=None,
                output_dir=Path(tmp),
                status=TaskStatus.PARSING,
                log=Mock(),
            )

            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_cancel_if_requested_marks_cancelled_and_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            write_task_status(
                task_id="task-1",
                output_dir=output_dir,
                status=TaskStatus.DOWNLOADING,
            )
            request_task_cancel(task_id="task-1", output_dir=output_dir)

            with self.assertRaises(TaskCancelledError):
                cancel_if_requested(task_id="task-1", output_dir=output_dir)

            payload = json.loads((output_dir / "task-1.status.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], TaskStatus.CANCELLED.value)

    def test_handle_task_exception_logs_and_marks_failed(self):
        update_status = Mock()
        log = Mock()

        handle_task_exception(
            task_id="task-1",
            exc=ValueError("boom"),
            update_status=update_status,
            log=log,
        )

        log.error.assert_called_once_with("任务异常 (task_id=task-1)", exc_info=True)
        update_status.assert_called_once_with("task-1", TaskStatus.FAILED, message="boom")


if __name__ == "__main__":
    unittest.main()
