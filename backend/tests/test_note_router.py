import unittest
from fastapi import HTTPException
from unittest.mock import Mock, patch

from app.enmus.note_enums import DownloadQuality
from app.models.notes_model import NoteResult
from app.routers.note import run_note_task


class TestNoteRouter(unittest.TestCase):
    def test_polished_transcript_task_requires_model_before_generation(self):
        fake_note = NoteResult(markdown="# 标题\n\n## 简体中文文字稿\n\n已有字幕", transcript=None, audio_meta=None)

        with patch("app.routers.note.NoteGenerator") as generator_cls, patch(
            "app.routers.note.save_note_to_file"
        ), patch("app.routers.note.task_serial_executor.run", side_effect=lambda fn: fn()), patch(
            "app.services.vector_store.VectorStoreManager.index_task"
        ):
            generator_cls.return_value.generate = Mock(return_value=fake_note)

            with self.assertRaises(HTTPException) as ctx:
                run_note_task(
                    task_id="subtitle-polished-task",
                    video_url="https://www.bilibili.com/video/BV123",
                    platform="bilibili",
                    quality=DownloadQuality.fast,
                    mode="polished_transcript",
                )

        self.assertEqual(ctx.exception.status_code, 400)
        generator_cls.return_value.generate.assert_not_called()

    def test_transcript_task_does_not_require_model_before_generation(self):
        fake_note = NoteResult(markdown="# 标题\n\n## 简体中文文字稿\n\n已有字幕", transcript=None, audio_meta=None)

        with patch("app.routers.note.NoteGenerator") as generator_cls, patch(
            "app.routers.note.save_note_to_file"
        ), patch("app.routers.note.task_serial_executor.run", side_effect=lambda fn: fn()), patch(
            "app.services.vector_store.VectorStoreManager.index_task"
        ):
            generator_cls.return_value.generate = Mock(return_value=fake_note)

            run_note_task(
                task_id="subtitle-transcript-task",
                video_url="https://www.bilibili.com/video/BV123",
                platform="bilibili",
                quality=DownloadQuality.fast,
                mode="transcript",
            )

        generator_cls.return_value.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
