import unittest

from app.enmus.task_status_enums import TaskStatus
from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services.note import NoteGenerator
from app.services.note_result_payload import (
    build_note_result,
    build_status_payload,
    format_exception_message,
)


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


class TestNoteResultPayload(unittest.TestCase):
    def test_build_note_result_prepends_source_link_once(self):
        transcript = _transcript()
        audio_meta = _audio_meta()
        result = build_note_result(
            markdown="# 测试视频\n\n正文",
            video_url="https://www.bilibili.com/video/BV123",
            transcript=transcript,
            audio_meta=audio_meta,
        )

        self.assertTrue(result.markdown.startswith("> 来源链接：https://www.bilibili.com/video/BV123\n\n"))
        self.assertIn("# 测试视频", result.markdown)
        self.assertIs(result.transcript, transcript)
        self.assertIs(result.audio_meta, audio_meta)
        self.assertEqual(result.audio_meta.video_id, "BV123")

        duplicated = build_note_result(
            markdown=result.markdown,
            video_url="https://www.bilibili.com/video/BV123",
            transcript=_transcript(),
            audio_meta=_audio_meta(),
        )
        self.assertEqual(duplicated.markdown, result.markdown)

    def test_note_generator_result_wrapper_keeps_legacy_private_hook(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        transcript = _transcript()
        audio_meta = _audio_meta()

        result = generator._build_note_result(
            markdown="# 测试视频",
            video_url="https://www.bilibili.com/video/BV123",
            transcript=transcript,
            audio_meta=audio_meta,
        )

        self.assertIn("> 来源链接：https://www.bilibili.com/video/BV123", result.markdown)
        self.assertIs(result.transcript, transcript)
        self.assertIs(result.audio_meta, audio_meta)

    def test_build_status_payload_normalizes_task_status_and_keeps_optional_fields(self):
        self.assertEqual(
            build_status_payload(
                task_id="task-1",
                status=TaskStatus.SUCCESS,
                message="完成",
                title="标题",
                platform="bilibili",
            ),
            {
                "task_id": "task-1",
                "status": TaskStatus.SUCCESS.value,
                "message": "完成",
                "title": "标题",
                "platform": "bilibili",
            },
        )

    def test_format_exception_message_uses_detail_and_serializes_dicts(self):
        class DetailError(Exception):
            detail = {"code": "bad", "message": "失败"}

        self.assertEqual(
            format_exception_message(DetailError("ignored")),
            '{"code": "bad", "message": "失败"}',
        )
        self.assertEqual(format_exception_message(ValueError("plain")), "plain")


if __name__ == "__main__":
    unittest.main()
