import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.routers.note import list_saved_tasks


class TestNoteTaskList(unittest.TestCase):
    def test_lists_only_polished_transcript_results_and_purges_legacy_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            polished_result_path = output_dir / "task-polished.json"
            polished_result_path.write_text(
                json.dumps(
                    {
                        "markdown": "# Demo\n\nhello",
                        "mode": "polished_transcript",
                        "audio_meta": {
                            "title": "Demo",
                            "platform": "bilibili",
                            "video_id": "BV123",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (output_dir / "task-polished.status.json").write_text(
                json.dumps({"status": "SUCCESS", "message": "done"}),
                encoding="utf-8",
            )
            (output_dir / "task-polished_transcript.json").write_text(
                json.dumps({"segments": []}),
                encoding="utf-8",
            )
            for legacy_task_id, markdown in (
                ("task-raw", "# Demo\n\n## 简体中文文字稿\n\nraw"),
                ("task-note", "# Demo\n\n## 要点总结\n\nlegacy note"),
            ):
                (output_dir / f"{legacy_task_id}.json").write_text(
                    json.dumps(
                        {
                            "markdown": markdown,
                            "audio_meta": {
                                "title": legacy_task_id,
                                "platform": "bilibili",
                                "video_id": legacy_task_id,
                            },
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                (output_dir / f"{legacy_task_id}.status.json").write_text(
                    json.dumps({"status": "SUCCESS", "message": "legacy"}),
                    encoding="utf-8",
                )

            with patch("app.routers.note.NOTE_OUTPUT_DIR", str(output_dir)):
                tasks = list_saved_tasks()

                self.assertFalse((output_dir / "task-raw.json").exists())
                self.assertFalse((output_dir / "task-raw.status.json").exists())
                self.assertFalse((output_dir / "task-note.json").exists())
                self.assertFalse((output_dir / "task-note.status.json").exists())

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_id"], "task-polished")
        self.assertEqual(tasks[0]["status"], "SUCCESS")
        self.assertEqual(tasks[0]["message"], "done")
        self.assertNotIn("## 校对文字稿", tasks[0]["result"]["markdown"])
        self.assertEqual(tasks[0]["result"]["audio_meta"]["title"], "Demo")


if __name__ == "__main__":
    unittest.main()
