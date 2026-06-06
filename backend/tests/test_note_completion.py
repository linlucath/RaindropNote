import unittest
from unittest.mock import Mock

from app.enmus.task_status_enums import TaskStatus
from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services.note_completion import complete_note_generation


def _audio_meta():
    return AudioDownloadResult(
        file_path="/tmp/demo.mp3",
        title="测试视频",
        duration=30,
        cover_url=None,
        platform="bilibili",
        video_id="BV123",
        raw_info={"webpage_url": "https://www.bilibili.com/video/BV123"},
    )


def _transcript():
    return TranscriptResult(
        language="zh",
        full_text="已有字幕",
        segments=[TranscriptSegment(start=0, end=1, text="已有字幕")],
    )


class TestNoteCompletion(unittest.TestCase):
    def test_complete_note_generation_updates_status_saves_metadata_and_returns_result(self):
        events = []

        def update_status(*args, **kwargs):
            events.append(("status", args, kwargs))

        def save_metadata(**kwargs):
            events.append(("save", kwargs))

        log = Mock()
        transcript = _transcript()
        audio_meta = _audio_meta()

        result = complete_note_generation(
            task_id="task-1",
            markdown="# 测试视频",
            video_url="https://www.bilibili.com/video/BV123",
            transcript=transcript,
            audio_meta=audio_meta,
            platform="bilibili",
            success_message="笔记生成成功",
            update_status=update_status,
            save_metadata=save_metadata,
            log=log,
        )

        self.assertEqual(
            events,
            [
                ("status", ("task-1", TaskStatus.SAVING), {"title": "测试视频", "platform": "bilibili"}),
                ("save", {"video_id": "BV123", "platform": "bilibili", "task_id": "task-1"}),
                ("status", ("task-1", TaskStatus.SUCCESS), {"title": "测试视频", "platform": "bilibili"}),
            ],
        )
        self.assertIn("> 来源链接：https://www.bilibili.com/video/BV123", result.markdown)
        self.assertIs(result.transcript, transcript)
        self.assertIs(result.audio_meta, audio_meta)
        log.info.assert_called_once_with("笔记生成成功 (task_id=task-1)")


if __name__ == "__main__":
    unittest.main()
