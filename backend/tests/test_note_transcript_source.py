import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services import note_transcript_source


def _subtitle_transcript(source: str = "bilibili_subtitle") -> TranscriptResult:
    return TranscriptResult(
        language="zh",
        full_text="已有字幕",
        segments=[TranscriptSegment(start=0, end=1, text="第一句")],
        raw={"source": source, "format": "srt"},
    )


def _cache_payload(source: str = "bilibili_subtitle") -> dict:
    return {
        "language": "zh",
        "full_text": "缓存字幕",
        "segments": [{"start": 0, "end": 1, "text": "缓存字幕"}],
        "raw": {"source": source, "format": "srt"},
    }


class TestNoteTranscriptSource(unittest.TestCase):
    def test_load_or_download_platform_transcript_prefers_valid_cache(self):
        downloader = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "task_transcript.json"
            cache_file.write_text(
                json.dumps(_cache_payload(), ensure_ascii=False),
                encoding="utf-8",
            )

            transcript = note_transcript_source.load_or_download_platform_transcript(
                transcript_cache_file=cache_file,
                downloader=downloader,
                video_url="https://www.bilibili.com/video/BV123",
            )

        self.assertEqual(transcript.full_text, "缓存字幕")
        downloader.download_subtitles.assert_not_called()

    def test_load_or_download_platform_transcript_ignores_audio_cache_and_downloads_subtitles(self):
        downloader = Mock()
        downloader.download_subtitles.return_value = _subtitle_transcript("youtube_transcript_api")

        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "task_transcript.json"
            cache_file.write_text(
                json.dumps(_cache_payload("audio_transcription"), ensure_ascii=False),
                encoding="utf-8",
            )

            transcript = note_transcript_source.load_or_download_platform_transcript(
                transcript_cache_file=cache_file,
                downloader=downloader,
                video_url="https://www.youtube.com/watch?v=abc123",
            )
            cached = json.loads(cache_file.read_text(encoding="utf-8"))

        self.assertEqual(transcript.raw["source"], "youtube_transcript_api")
        self.assertEqual(cached["raw"]["source"], "youtube_transcript_api")
        downloader.download_subtitles.assert_called_once_with("https://www.youtube.com/watch?v=abc123")

    def test_load_or_download_platform_transcript_returns_none_for_empty_or_failed_download(self):
        log = Mock()
        downloader = Mock()
        downloader.download_subtitles.side_effect = [
            TranscriptResult(language="zh", full_text="", segments=[], raw={"source": "bilibili_subtitle"}),
            RuntimeError("network failed"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "task_transcript.json"

            empty_result = note_transcript_source.load_or_download_platform_transcript(
                transcript_cache_file=cache_file,
                downloader=downloader,
                video_url="https://www.bilibili.com/video/BV123",
                log=log,
            )
            failed_result = note_transcript_source.load_or_download_platform_transcript(
                transcript_cache_file=cache_file,
                downloader=downloader,
                video_url="https://www.bilibili.com/video/BV123",
                log=log,
            )

        self.assertIsNone(empty_result)
        self.assertIsNone(failed_result)
        self.assertFalse(cache_file.exists())
        self.assertTrue(log.warning.called)


if __name__ == "__main__":
    unittest.main()
