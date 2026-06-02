import unittest
from unittest.mock import Mock, patch

from app.enmus.note_enums import DownloadQuality
from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services.note import NoteGenerator


def _audio_meta():
    return AudioDownloadResult(
        file_path="/tmp/demo.mp3",
        title="測試視頻",
        duration=30,
        cover_url=None,
        platform="bilibili",
        video_id="BV123",
        raw_info={"webpage_url": "https://www.bilibili.com/video/BV123"},
    )


def _transcript():
    return TranscriptResult(
        language="zh",
        full_text="這個視頻講學習。後面還補充了一個觀點。",
        segments=[
            TranscriptSegment(start=3, end=8, text="這個視頻講學習。"),
            TranscriptSegment(start=12, end=18, text="後面還補充了一個觀點。"),
        ],
    )


def _subtitle_transcript():
    transcript = _transcript()
    transcript.raw = {"source": "bilibili_subtitle"}
    return transcript


def _youtube_subtitle_transcript():
    transcript = _transcript()
    transcript.raw = {"source": "youtube_transcript_api", "language_code": "en"}
    return transcript


def _audio_transcript():
    transcript = _transcript()
    transcript.raw = {"source": "audio_transcription"}
    return transcript


class TestTranscriptOnlyMode(unittest.TestCase):
    def test_builds_readable_simplified_transcript_markdown(self):
        markdown = NoteGenerator._build_transcript_markdown(_audio_meta(), _transcript())

        self.assertIn("# 测试视频", markdown)
        self.assertIn("## 简体中文文字稿", markdown)
        self.assertIn("这个视频讲学习。后面还补充了一个观点。", markdown)
        self.assertIn("## 带时间戳文字稿", markdown)
        self.assertIn("[00:03] 这个视频讲学习。", markdown)
        self.assertIn("[00:12] 后面还补充了一个观点。", markdown)

    def test_transcript_mode_skips_gpt_summary(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        generator.video_img_urls = []
        generator.video_path = None
        generator._update_status = Mock()
        downloader = Mock()
        downloader.download_subtitles.return_value = _subtitle_transcript()
        generator._get_downloader = Mock(return_value=downloader)
        generator._get_gpt = Mock(side_effect=AssertionError("GPT should not be used"))
        generator._download_media = Mock(return_value=_audio_meta())
        generator._summarize_text = Mock(side_effect=AssertionError("summary should not be used"))
        generator._save_metadata = Mock()

        result = generator.generate(
            video_url="https://www.bilibili.com/video/BV123",
            platform="bilibili",
            quality=DownloadQuality.fast,
            task_id="transcript-task",
            mode="transcript",
        )

        self.assertIsNotNone(result)
        self.assertIn("## 简体中文文字稿", result.markdown)
        generator._get_gpt.assert_not_called()
        generator._summarize_text.assert_not_called()
        generator._save_metadata.assert_called_once_with(
            video_id="BV123",
            platform="bilibili",
            task_id="transcript-task",
        )

    def test_polished_transcript_mode_skips_gpt_for_downloaded_subtitles(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        generator.video_img_urls = []
        generator.video_path = None
        generator._update_status = Mock()
        downloader = Mock()
        downloader.download_subtitles.return_value = _subtitle_transcript()
        generator._get_downloader = Mock(return_value=downloader)
        gpt = Mock()
        gpt.polish_transcript.return_value = "这是校对后的字幕文字稿。"
        generator._get_gpt = Mock(return_value=gpt)
        generator._download_media = Mock(return_value=_audio_meta())
        generator._summarize_text = Mock(side_effect=AssertionError("summary should not be used"))
        generator._save_metadata = Mock()

        result = generator.generate(
            video_url="https://www.bilibili.com/video/BV123",
            platform="bilibili",
            quality=DownloadQuality.fast,
            task_id="subtitle-polished-transcript-task",
            mode="polished_transcript",
        )

        self.assertIsNotNone(result)
        self.assertNotIn("## 校对文字稿", result.markdown)
        self.assertIn("# 测试视频", result.markdown)
        self.assertIn("这是校对后的字幕文字稿。", result.markdown)
        self.assertNotIn("## 带时间戳文字稿", result.markdown)
        gpt.polish_transcript.assert_called_once()
        generator._summarize_text.assert_not_called()

    def test_polished_transcript_mode_fails_without_platform_subtitles(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        generator.video_img_urls = []
        generator.video_path = None
        generator._update_status = Mock()
        downloader = Mock()
        downloader.download_subtitles.return_value = None
        generator._get_downloader = Mock(return_value=downloader)
        gpt = Mock()
        generator._get_gpt = Mock(return_value=gpt)
        generator._download_media = Mock(side_effect=AssertionError("should not download media"))
        generator._summarize_text = Mock(side_effect=AssertionError("summary should not be used"))
        generator._save_metadata = Mock()

        result = generator.generate(
            video_url="https://www.bilibili.com/video/BV123",
            platform="bilibili",
            quality=DownloadQuality.fast,
            task_id="polished-transcript-task",
            model_name="demo-model",
            provider_id="demo-provider",
            mode="polished_transcript",
        )

        self.assertIsNone(result)
        generator._download_media.assert_not_called()
        gpt.polish_transcript.assert_not_called()
        generator._summarize_text.assert_not_called()

    def test_youtube_polished_transcript_mode_does_not_probe_media_when_subtitles_exist(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        generator.video_img_urls = []
        generator.video_path = None
        generator._update_status = Mock()
        downloader = Mock()
        downloader.download_subtitles.return_value = _youtube_subtitle_transcript()
        generator._get_downloader = Mock(return_value=downloader)
        gpt = Mock()
        gpt.polish_transcript.return_value = "polished subtitle text"
        generator._get_gpt = Mock(return_value=gpt)
        generator._download_media = Mock(side_effect=AssertionError("should not probe media"))
        generator._summarize_text = Mock(side_effect=AssertionError("summary should not be used"))
        generator._save_metadata = Mock()

        result = generator.generate(
            video_url="https://www.youtube.com/watch?v=Q2um0Vvmtj0",
            platform="youtube",
            quality=DownloadQuality.fast,
            task_id="youtube-subtitle-only-task",
            model_name="demo-model",
            provider_id="demo-provider",
            mode="polished_transcript",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.audio_meta.platform, "youtube")
        self.assertEqual(result.audio_meta.video_id, "Q2um0Vvmtj0")
        self.assertEqual(result.audio_meta.file_path, "")
        generator._download_media.assert_not_called()
        gpt.polish_transcript.assert_called_once()

    def test_youtube_subtitle_only_meta_fetches_title_without_media_probe(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        generator.video_img_urls = []
        generator.video_path = None
        generator._update_status = Mock()
        downloader = Mock()
        downloader.download_subtitles.return_value = _youtube_subtitle_transcript()
        generator._get_downloader = Mock(return_value=downloader)
        gpt = Mock()
        gpt.polish_transcript.return_value = "polished subtitle text"
        generator._get_gpt = Mock(return_value=gpt)
        generator._download_media = Mock(side_effect=AssertionError("should not probe media"))
        generator._summarize_text = Mock(side_effect=AssertionError("summary should not be used"))
        generator._save_metadata = Mock()

        with patch("app.services.note.NoteGenerator._fetch_video_title", return_value="Warm People") as fetch_title:
            result = generator.generate(
                video_url="https://www.youtube.com/watch?v=Q2um0Vvmtj0",
                platform="youtube",
                quality=DownloadQuality.fast,
                task_id="youtube-subtitle-title-task",
                model_name="demo-model",
                provider_id="demo-provider",
                mode="polished_transcript",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.audio_meta.title, "Warm People")
        fetch_title.assert_called_once_with(
            "https://www.youtube.com/watch?v=Q2um0Vvmtj0",
            "youtube",
        )


if __name__ == "__main__":
    unittest.main()
