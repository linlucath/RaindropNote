import unittest
from unittest.mock import Mock, patch

from app import create_app
from app.enmus.note_enums import DownloadQuality
from app.models.notes_model import NoteResult
from app.routers.note import run_note_task


class TestChatAndIndexRemoval(unittest.TestCase):
    def test_app_no_longer_registers_chat_routes(self):
        app = create_app(lifespan=None)
        route_paths = {route.path for route in app.routes}

        self.assertNotIn("/api/chat/index", route_paths)
        self.assertNotIn("/api/chat/status", route_paths)
        self.assertNotIn("/api/chat/ask", route_paths)

    def test_run_note_task_no_longer_indexes_for_chat(self):
        fake_note = NoteResult(markdown="# 标题", transcript=None, audio_meta=None)

        with patch("app.routers.note.NoteGenerator") as generator_cls, patch(
            "app.routers.note.save_note_to_file"
        ), patch("app.routers.note.task_serial_executor.run", side_effect=lambda fn: fn()):
            generator_cls.return_value.generate = Mock(return_value=fake_note)

            run_note_task(
                task_id="note-task-without-chat-index",
                video_url="https://www.bilibili.com/video/BV123",
                platform="bilibili",
                quality=DownloadQuality.fast,
                mode="transcript",
            )


if __name__ == "__main__":
    unittest.main()
