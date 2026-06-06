import unittest
from unittest.mock import Mock, patch

from app.services import note_records


class TestNoteRecords(unittest.TestCase):
    def test_delete_note_record_prefers_task_id(self):
        log = Mock()

        with patch("app.services.note_records.delete_task_by_task_id", return_value=2) as delete_by_task:
            with patch("app.services.note_records.delete_task_by_video") as delete_by_video:
                result = note_records.delete_note_record(
                    video_id="BV123",
                    platform="bilibili",
                    task_id="task-1",
                    log=log,
                )

        self.assertEqual(result, 2)
        delete_by_task.assert_called_once_with("task-1")
        delete_by_video.assert_not_called()
        log.info.assert_called_once_with("删除笔记记录 (task_id=task-1)")

    def test_delete_note_record_requires_video_and_platform_without_task_id(self):
        log = Mock()

        result = note_records.delete_note_record(video_id="BV123", platform=None, task_id=None, log=log)

        self.assertEqual(result, 0)
        log.warning.assert_called_once_with("删除笔记记录失败：缺少 task_id，且未提供完整的 video_id/platform")

    def test_save_note_record_logs_database_errors(self):
        log = Mock()

        with patch("app.services.note_records.insert_video_task", side_effect=RuntimeError("db down")):
            note_records.save_note_record(
                video_id="BV123",
                platform="bilibili",
                task_id="task-1",
                log=log,
            )

        log.error.assert_called_once_with("保存任务记录失败：db down")


if __name__ == "__main__":
    unittest.main()
