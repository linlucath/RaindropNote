import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.models.audio_model import AudioDownloadResult
from app.models.gpt_model import GPTSource
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services import note_llm_markdown


def _audio_meta(title: str | None = "繁體 視頻") -> AudioDownloadResult:
    return AudioDownloadResult(
        file_path="/tmp/demo.mp3",
        title=title,
        duration=120,
        cover_url=None,
        platform="bilibili",
        video_id="BV123",
        raw_info={"tags": ["ai", "notes"]},
    )


def _transcript(language: str | None = "zh") -> TranscriptResult:
    return TranscriptResult(
        language=language,
        full_text="full text",
        segments=[
            TranscriptSegment(start=0, end=1, text="hello"),
            TranscriptSegment(start=1, end=2, text="world"),
        ],
    )


class TestNoteLlmMarkdown(unittest.TestCase):
    def test_build_polish_transcript_source_matches_note_generator_fields(self):
        cache_file = Path("/tmp/task-123.md")
        audio_meta = _audio_meta()
        transcript = _transcript("en")

        source = note_llm_markdown.build_polish_transcript_source(
            audio_meta=audio_meta,
            transcript=transcript,
            markdown_cache_file=cache_file,
        )

        self.assertIsInstance(source, GPTSource)
        self.assertEqual(source.title, "繁體 視頻")
        self.assertIs(source.segment, transcript.segments)
        self.assertEqual(source.tags, ["ai", "notes"])
        self.assertEqual(source.language, "en")
        self.assertEqual(source.checkpoint_key, "task-123")
        self.assertFalse(source.screenshot)
        self.assertFalse(source.link)

    def test_polish_transcript_markdown_strips_output_prepends_normalized_title_and_writes_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "abc123.md"
            gpt = Mock()
            gpt.polish_transcript.return_value = "\n\n## 阅读导览\n\n正文内容\n\n"

            markdown = note_llm_markdown.polish_transcript_markdown(
                audio_meta=_audio_meta("繁體 視頻"),
                transcript=_transcript("zh"),
                gpt=gpt,
                markdown_cache_file=cache_file,
            )

            source = gpt.polish_transcript.call_args.args[0]
            cached_markdown = cache_file.read_text(encoding="utf-8")

        self.assertEqual(markdown, "# 繁体视频\n\n## 阅读导览\n\n正文内容")
        self.assertEqual(cached_markdown, markdown)
        self.assertEqual(source.checkpoint_key, "abc123")
        self.assertEqual(source.language, "zh")

    def test_polish_transcript_markdown_uses_unnamed_video_title_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "fallback.md"
            gpt = Mock()
            gpt.polish_transcript.return_value = "正文"

            markdown = note_llm_markdown.polish_transcript_markdown(
                audio_meta=_audio_meta(None),
                transcript=_transcript(),
                gpt=gpt,
                markdown_cache_file=cache_file,
            )

        self.assertEqual(markdown, "# 未命名视频\n\n正文")

    def test_polish_transcript_markdown_creates_cache_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "nested" / "fallback.md"
            gpt = Mock()
            gpt.polish_transcript.return_value = "正文"

            note_llm_markdown.polish_transcript_markdown(
                audio_meta=_audio_meta(None),
                transcript=_transcript(),
                gpt=gpt,
                markdown_cache_file=cache_file,
            )

            self.assertEqual(cache_file.read_text(encoding="utf-8"), "# 未命名视频\n\n正文")

    def test_build_summarize_source_matches_note_generator_fields(self):
        cache_file = Path("/tmp/summary-task.md")
        audio_meta = _audio_meta("Summary Title")
        transcript = _transcript("en")
        formats = ["link", "screenshot"]
        video_img_urls = ["https://example.com/cover.jpg"]

        source = note_llm_markdown.build_summarize_source(
            audio_meta=audio_meta,
            transcript=transcript,
            markdown_cache_file=cache_file,
            link=True,
            screenshot=True,
            formats=formats,
            style="outline",
            extras="extra instructions",
            video_img_urls=video_img_urls,
        )

        self.assertIsInstance(source, GPTSource)
        self.assertEqual(source.title, "Summary Title")
        self.assertIs(source.segment, transcript.segments)
        self.assertEqual(source.tags, ["ai", "notes"])
        self.assertTrue(source.screenshot)
        self.assertIs(source.video_img_urls, video_img_urls)
        self.assertTrue(source.link)
        self.assertIs(source._format, formats)
        self.assertEqual(source.style, "outline")
        self.assertEqual(source.extras, "extra instructions")
        self.assertEqual(source.checkpoint_key, "summary-task")
        self.assertIsNone(source.language)

    def test_summarize_note_markdown_calls_gpt_and_writes_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "summary-cache.md"
            gpt = Mock()
            gpt.summarize.return_value = "# Summary\n\nBody"

            markdown = note_llm_markdown.summarize_note_markdown(
                audio_meta=_audio_meta("Summary Title"),
                transcript=_transcript("en"),
                gpt=gpt,
                markdown_cache_file=cache_file,
                link=False,
                screenshot=True,
                formats=["screenshot"],
                style=None,
                extras=None,
                video_img_urls=["https://example.com/1.jpg"],
            )

            source = gpt.summarize.call_args.args[0]
            cached_markdown = cache_file.read_text(encoding="utf-8")

        self.assertEqual(markdown, "# Summary\n\nBody")
        self.assertEqual(cached_markdown, markdown)
        self.assertEqual(source.checkpoint_key, "summary-cache")
        self.assertTrue(source.screenshot)
        self.assertFalse(source.link)
        self.assertIsNone(source.language)

    def test_summarize_note_markdown_creates_cache_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "nested" / "summary-cache.md"
            gpt = Mock()
            gpt.summarize.return_value = "# Summary\n\nBody"

            markdown = note_llm_markdown.summarize_note_markdown(
                audio_meta=_audio_meta("Summary Title"),
                transcript=_transcript("en"),
                gpt=gpt,
                markdown_cache_file=cache_file,
                link=False,
                screenshot=False,
                formats=[],
                style=None,
                extras=None,
                video_img_urls=[],
            )

            self.assertEqual(cache_file.read_text(encoding="utf-8"), markdown)


if __name__ == "__main__":
    unittest.main()
