import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.routers.note import list_saved_tasks


class TestNoteTaskList(unittest.TestCase):
    def test_lists_saved_note_results_without_auxiliary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            result_path = output_dir / "task-1.json"
            result_path.write_text(
                json.dumps(
                    {
                        "markdown": "hello",
                        "audio_meta": {
                            "title": "Demo",
                            "platform": "bilibili",
                            "video_id": "BV123",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (output_dir / "task-1.status.json").write_text(
                json.dumps({"status": "SUCCESS", "message": "done"}),
                encoding="utf-8",
            )
            (output_dir / "task-1_transcript.json").write_text(
                json.dumps({"segments": []}),
                encoding="utf-8",
            )

            with patch("app.routers.note.NOTE_OUTPUT_DIR", str(output_dir)):
                tasks = list_saved_tasks()

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_id"], "task-1")
        self.assertEqual(tasks[0]["status"], "SUCCESS")
        self.assertEqual(tasks[0]["message"], "done")
        self.assertEqual(tasks[0]["result"]["audio_meta"]["title"], "Demo")


if __name__ == "__main__":
    unittest.main()
