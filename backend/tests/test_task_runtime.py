import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.enmus.task_status_enums import TaskStatus
from app.services import task_runtime


class TestTaskRuntime(unittest.TestCase):
    def test_note_and_batch_output_dirs_come_from_note_output_env(self):
        with patch.dict(os.environ, {"NOTE_OUTPUT_DIR": "/tmp/bilinote-notes"}):
            note_dir = task_runtime.default_note_output_dir()

        self.assertEqual(note_dir, Path("/tmp/bilinote-notes"))
        self.assertEqual(
            task_runtime.default_batch_output_dir(note_dir),
            Path("/tmp/bilinote-notes") / "batches",
        )

    def test_default_batch_output_dir_derives_from_current_env(self):
        with patch.dict(os.environ, {"NOTE_OUTPUT_DIR": "/tmp/runtime-notes"}):
            batch_dir = task_runtime.default_batch_output_dir()

        self.assertEqual(batch_dir, Path("/tmp/runtime-notes") / "batches")

    def test_status_sets_share_task_status_values(self):
        self.assertEqual(task_runtime.SUPPORTED_GENERATION_MODE, "polished_transcript")
        self.assertIn(TaskStatus.CANCELLING.value, task_runtime.ACTIVE_TASK_STATUSES)
        self.assertNotIn(TaskStatus.SUCCESS.value, task_runtime.ACTIVE_TASK_STATUSES)
        self.assertEqual(
            task_runtime.TERMINAL_TASK_STATUSES,
            {
                TaskStatus.SUCCESS.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
            },
        )
        self.assertEqual(task_runtime.TERMINAL_BATCH_STATUSES, task_runtime.TERMINAL_TASK_STATUSES)
        self.assertIn("SKIPPED", task_runtime.COMPLETED_ITEM_STATUSES)


if __name__ == "__main__":
    unittest.main()
