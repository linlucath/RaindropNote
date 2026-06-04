import json
import tempfile
import unittest
from pathlib import Path

from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services import subtitle_transcripts


def _subtitle_payload(source: str = "bilibili_subtitle") -> dict:
    return {
        "language": "zh",
        "full_text": "已有字幕",
        "segments": [
            {"start": 0, "end": 1, "text": "第一句"},
            {"start": 2, "end": 3, "text": "第二句"},
        ],
        "raw": {"source": source, "format": "srt"},
    }


class TestSubtitleTranscripts(unittest.TestCase):
    def test_detects_supported_subtitle_transcript_sources(self):
        self.assertTrue(subtitle_transcripts.is_subtitle_transcript_data(
            _subtitle_payload("bilibili_subtitle"),
        ))
        self.assertFalse(subtitle_transcripts.is_subtitle_transcript_data(
            _subtitle_payload("audio_transcription"),
        ))

        transcript = TranscriptResult(
            language="zh",
            full_text="已有字幕",
            segments=[TranscriptSegment(start=0, end=1, text="第一句")],
            raw={"source": "youtube_transcript_api"},
        )
        self.assertTrue(subtitle_transcripts.is_subtitle_transcript_result(transcript))

    def test_load_subtitle_transcript_cache_returns_transcript_result_for_platform_subtitles(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "task_transcript.json"
            cache_file.write_text(
                json.dumps(_subtitle_payload(), ensure_ascii=False),
                encoding="utf-8",
            )

            transcript = subtitle_transcripts.load_subtitle_transcript_cache(cache_file)

        self.assertIsInstance(transcript, TranscriptResult)
        self.assertEqual(transcript.language, "zh")
        self.assertEqual(transcript.full_text, "已有字幕")
        self.assertEqual(len(transcript.segments), 2)
        self.assertEqual(transcript.segments[1].text, "第二句")
        self.assertEqual(transcript.raw["source"], "bilibili_subtitle")

    def test_load_subtitle_transcript_cache_ignores_audio_transcription_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "task_transcript.json"
            cache_file.write_text(
                json.dumps(_subtitle_payload("audio_transcription"), ensure_ascii=False),
                encoding="utf-8",
            )

            transcript = subtitle_transcripts.load_subtitle_transcript_cache(cache_file)

        self.assertIsNone(transcript)


if __name__ == "__main__":
    unittest.main()
