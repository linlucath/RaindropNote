import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services.note import NoteGenerator
from app.services.progress_state import read_task_status, request_task_cancel, write_task_status


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


class TestAudioTranscriptionConfirmation(unittest.TestCase):
    def test_generate_stops_at_cancel_checkpoints_before_next_stage(self):
        checkpoints = [
            ('after_parsing', 'note'),
            ('after_subtitles', 'note'),
            ('after_download', 'note'),
            ('after_summarizing', 'note'),
            ('before_saving', 'transcript'),
        ]

        import app.services.note as note_service

        for checkpoint, mode in checkpoints:
            with self.subTest(checkpoint=checkpoint):
                generator = NoteGenerator.__new__(NoteGenerator)
                generator.video_img_urls = []
                generator.video_path = None
                generator._save_metadata = Mock()
                generator._post_process_markdown = Mock(side_effect=AssertionError('should not post process'))
                generator._get_gpt = Mock(return_value=Mock())

                downloader = Mock()

                with tempfile.TemporaryDirectory() as tmp:
                    output_dir = Path(tmp)
                    original_output_dir = note_service.NOTE_OUTPUT_DIR
                    note_service.NOTE_OUTPUT_DIR = output_dir

                    task_id = f'{checkpoint}-task'
                    write_task_status(
                        task_id=task_id,
                        output_dir=output_dir,
                        status=TaskStatus.PENDING,
                        title='检查点测试',
                        platform='bilibili',
                    )

                    def cancel_now():
                        request_task_cancel(task_id=task_id, output_dir=output_dir)

                    def download_subtitles(_video_url):
                        if checkpoint == 'after_subtitles':
                            cancel_now()
                        return _transcript()

                    downloader.download_subtitles.side_effect = download_subtitles

                    if checkpoint == 'after_parsing':
                        generator._get_downloader = Mock(side_effect=lambda _platform: (cancel_now(), downloader)[1])
                        generator._download_media = Mock(side_effect=AssertionError('should not download media'))
                        generator._get_transcript = Mock(side_effect=AssertionError('should not get transcript'))
                        generator._summarize_text = Mock(side_effect=AssertionError('should not summarize'))
                    else:
                        generator._get_downloader = Mock(return_value=downloader)

                        def download_media(**_kwargs):
                            if checkpoint == 'after_download':
                                cancel_now()
                            return _audio_meta()

                        def get_transcript(**_kwargs):
                            if checkpoint == 'after_transcription':
                                cancel_now()
                            return _transcript()

                        def summarize_text(**_kwargs):
                            if checkpoint == 'after_summarizing':
                                cancel_now()
                            return '# 总结'

                        def build_transcript_markdown(*_args, **_kwargs):
                            if checkpoint == 'before_saving':
                                cancel_now()
                            return '# 标题\n\n## 简体中文文字稿\n\n已有字幕'

                        if checkpoint == 'after_subtitles':
                            generator._download_media = Mock(side_effect=AssertionError('should not download media'))
                        else:
                            generator._download_media = Mock(side_effect=download_media)
                        generator._get_transcript = Mock(side_effect=get_transcript)
                        generator._summarize_text = Mock(side_effect=summarize_text)
                        generator._build_transcript_markdown = Mock(side_effect=build_transcript_markdown)

                    try:
                        result = generator.generate(
                            video_url='https://www.bilibili.com/video/BV123',
                            platform='bilibili',
                            quality=DownloadQuality.fast,
                            task_id=task_id,
                            model_name='demo-model',
                            provider_id='demo-provider',
                            mode=mode,
                            output_path='/tmp',
                        )
                    finally:
                        note_service.NOTE_OUTPUT_DIR = original_output_dir

                    self.assertIsNone(result)
                    self.assertEqual(
                        read_task_status(task_id=task_id, output_dir=output_dir).get('status'),
                        TaskStatus.CANCELLED.value,
                    )
                    generator._save_metadata.assert_not_called()

    def test_generate_fails_when_platform_subtitles_are_unavailable(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        generator.video_img_urls = []
        generator.video_path = None
        generator._update_status = Mock()
        downloader = Mock()
        downloader.download_subtitles.return_value = None
        generator._get_downloader = Mock(return_value=downloader)
        generator._get_gpt = Mock(return_value=Mock())
        generator._download_media = Mock(side_effect=AssertionError("should not download media"))
        generator._get_transcript = Mock(side_effect=AssertionError("should not get transcript"))
        generator._save_metadata = Mock()

        result = generator.generate(
            video_url="https://www.bilibili.com/video/BV123",
            platform="bilibili",
            quality=DownloadQuality.fast,
            task_id="needs-confirmation",
            model_name="demo-model",
            provider_id="demo-provider",
            mode="note",
            output_path="/tmp",
        )

        self.assertIsNone(result)
        generator._download_media.assert_not_called()
        generator._get_transcript.assert_not_called()
        generator._update_status.assert_any_call(
            "needs-confirmation",
            TaskStatus.FAILED,
            message=NoteGenerator.SUBTITLE_REQUIRED_MESSAGE,
            platform='bilibili',
        )

    def test_generate_ignores_cached_audio_transcription_results(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        generator.video_img_urls = []
        generator.video_path = None
        generator._update_status = Mock()
        downloader = Mock()
        downloader.download_subtitles.return_value = None
        generator._get_downloader = Mock(return_value=downloader)
        generator._get_gpt = Mock(return_value=Mock())
        generator._download_media = Mock(side_effect=AssertionError("should not download media"))
        generator._get_transcript = Mock(side_effect=AssertionError("should not get transcript"))
        generator._save_metadata = Mock()

        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "cached-task_transcript.json"
            cache_file.write_text(
                json.dumps({
                    "language": "zh",
                    "full_text": "音频转写缓存",
                    "segments": [{"start": 0, "end": 1, "text": "音频转写缓存"}],
                    "raw": {"source": "audio_transcription"},
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            import app.services.note as note_service
            original_output_dir = note_service.NOTE_OUTPUT_DIR
            note_service.NOTE_OUTPUT_DIR = Path(tmp)
            try:
                result = generator.generate(
                    video_url="https://www.bilibili.com/video/BV123",
                    platform="bilibili",
                    quality=DownloadQuality.fast,
                    task_id="cached-task",
                    model_name="demo-model",
                    provider_id="demo-provider",
                    mode="note",
                    output_path="/tmp",
                )
            finally:
                note_service.NOTE_OUTPUT_DIR = original_output_dir

        self.assertIsNone(result)
        generator._download_media.assert_not_called()
        generator._get_transcript.assert_not_called()

    def test_generate_does_not_accept_audio_transcription_even_when_requested(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        generator.video_img_urls = []
        generator.video_path = None
        generator._update_status = Mock()
        downloader = Mock()
        downloader.download_subtitles.return_value = None
        generator._get_downloader = Mock(return_value=downloader)
        generator._get_gpt = Mock(side_effect=AssertionError("GPT should not be used"))
        generator._download_media = Mock(side_effect=AssertionError("should not download media"))
        generator._get_transcript = Mock(side_effect=AssertionError("should not get transcript"))
        generator._save_metadata = Mock()

        result = generator.generate(
            video_url="https://www.bilibili.com/video/BV123",
            platform="bilibili",
            quality=DownloadQuality.fast,
            task_id="confirmed",
            mode="transcript",
            output_path="/tmp",
        )

        self.assertIsNone(result)
        generator._download_media.assert_not_called()
        generator._get_transcript.assert_not_called()


if __name__ == "__main__":
    unittest.main()
