import unittest
from unittest.mock import Mock

from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services import subtitle_audio_meta


def _subtitle_transcript(raw: dict | None = None) -> TranscriptResult:
    return TranscriptResult(
        language="zh",
        full_text="已有字幕",
        segments=[
            TranscriptSegment(start=0, end=1.5, text="第一句"),
            TranscriptSegment(start=2, end=7.25, text="第二句"),
        ],
        raw=raw or {"source": "youtube_transcript_api"},
    )


class TestSubtitleAudioMeta(unittest.TestCase):
    def test_detects_supported_subtitle_transcript_data_and_results(self):
        self.assertTrue(subtitle_audio_meta.is_subtitle_transcript_data({
            "raw": {"source": "bilibili_subtitle"},
        }))
        self.assertTrue(subtitle_audio_meta.is_subtitle_transcript_result(
            _subtitle_transcript({"source": "youtube_transcript_api"}),
        ))
        self.assertFalse(subtitle_audio_meta.is_subtitle_transcript_data({
            "raw": {"source": "audio_transcription"},
        }))

    def test_builds_subtitle_only_audio_meta_from_raw_transcript_fields(self):
        transcript = _subtitle_transcript({
            "source": "youtube_transcript_api",
            "title": "字幕标题",
            "thumbnail": "https://example.com/cover.jpg",
            "tags": ["学习", "AI"],
        })

        audio_meta = subtitle_audio_meta.build_subtitle_only_audio_meta(
            video_url="https://www.youtube.com/watch?v=Q2um0Vvmtj0",
            platform="youtube",
            transcript=transcript,
            title_lookup=Mock(side_effect=AssertionError("title should come from raw data")),
        )

        self.assertIsInstance(audio_meta, AudioDownloadResult)
        self.assertEqual(audio_meta.file_path, "")
        self.assertEqual(audio_meta.title, "字幕标题")
        self.assertEqual(audio_meta.duration, 7.25)
        self.assertEqual(audio_meta.cover_url, "https://example.com/cover.jpg")
        self.assertEqual(audio_meta.platform, "youtube")
        self.assertEqual(audio_meta.video_id, "Q2um0Vvmtj0")
        self.assertEqual(audio_meta.raw_info["tags"], ["学习", "AI"])
        self.assertEqual(audio_meta.raw_info["subtitle_source"], "youtube_transcript_api")

    def test_builds_subtitle_only_audio_meta_uses_title_lookup_then_video_id(self):
        title_lookup = Mock(return_value="Lookup Title")

        audio_meta = subtitle_audio_meta.build_subtitle_only_audio_meta(
            video_url="https://www.youtube.com/watch?v=Q2um0Vvmtj0",
            platform="youtube",
            transcript=_subtitle_transcript({"source": "youtube_transcript_api"}),
            title_lookup=title_lookup,
        )

        self.assertEqual(audio_meta.title, "Lookup Title")
        title_lookup.assert_called_once_with(
            "https://www.youtube.com/watch?v=Q2um0Vvmtj0",
            "youtube",
        )

        fallback_meta = subtitle_audio_meta.build_subtitle_only_audio_meta(
            video_url="https://www.youtube.com/watch?v=Q2um0Vvmtj0",
            platform="youtube",
            transcript=_subtitle_transcript({"source": "youtube_transcript_api"}),
            title_lookup=Mock(return_value=None),
        )
        self.assertEqual(fallback_meta.title, "Q2um0Vvmtj0")

    def test_fetch_youtube_video_title_uses_oembed_only_for_youtube(self):
        requests_get = Mock()
        response = Mock()
        response.json.return_value = {"title": "OEmbed Title"}
        response.raise_for_status.return_value = None
        requests_get.return_value = response

        title = subtitle_audio_meta.fetch_video_title(
            "https://www.youtube.com/watch?v=Q2um0Vvmtj0",
            "youtube",
            requests_get=requests_get,
        )

        self.assertEqual(title, "OEmbed Title")
        self.assertEqual(requests_get.call_args.args[0], "https://www.youtube.com/oembed")

        self.assertIsNone(subtitle_audio_meta.fetch_video_title(
            "https://www.bilibili.com/video/BV123",
            "bilibili",
            requests_get=requests_get,
        ))
        self.assertEqual(requests_get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
