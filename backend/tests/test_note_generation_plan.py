import unittest
from pathlib import Path

from app.services import note_generation_plan


class TestNoteGenerationPlan(unittest.TestCase):
    def test_build_cache_paths_uses_runtime_output_dir_and_task_id(self):
        paths = note_generation_plan.build_cache_paths(Path("/tmp/runtime-notes"), "task-123")

        self.assertEqual(paths.audio_cache_file, Path("/tmp/runtime-notes/task-123_audio.json"))
        self.assertEqual(paths.transcript_cache_file, Path("/tmp/runtime-notes/task-123_transcript.json"))
        self.assertEqual(paths.markdown_cache_file, Path("/tmp/runtime-notes/task-123_markdown.md"))

    def test_prepare_mode_branch_uses_legacy_exact_mode_checks(self):
        transcript = note_generation_plan.prepare_mode_branch("transcript")
        polished = note_generation_plan.prepare_mode_branch("polished_transcript")
        note = note_generation_plan.prepare_mode_branch("note")
        missing = note_generation_plan.prepare_mode_branch(None)

        self.assertTrue(transcript.is_transcript_only)
        self.assertFalse(transcript.is_polished_transcript)
        self.assertTrue(polished.is_polished_transcript)
        self.assertFalse(polished.is_transcript_only)
        self.assertFalse(note.is_transcript_only)
        self.assertFalse(note.is_polished_transcript)
        self.assertFalse(missing.is_transcript_only)
        self.assertFalse(missing.is_polished_transcript)

    def test_prepare_media_source_matches_subtitle_only_and_probe_branches(self):
        youtube_subtitle_only = note_generation_plan.prepare_media_source(
            platform="youtube",
            screenshot=False,
            video_understanding=False,
        )
        bilibili_metadata_probe = note_generation_plan.prepare_media_source(
            platform="bilibili",
            screenshot=False,
            video_understanding=False,
        )
        youtube_full_download = note_generation_plan.prepare_media_source(
            platform="youtube",
            screenshot=True,
            video_understanding=False,
        )

        self.assertTrue(youtube_subtitle_only.use_subtitle_only_audio_meta)
        self.assertTrue(youtube_subtitle_only.skip_download)
        self.assertFalse(bilibili_metadata_probe.use_subtitle_only_audio_meta)
        self.assertTrue(bilibili_metadata_probe.skip_download)
        self.assertFalse(youtube_full_download.use_subtitle_only_audio_meta)
        self.assertFalse(youtube_full_download.skip_download)
        self.assertTrue(youtube_full_download.need_full_download)


if __name__ == "__main__":
    unittest.main()
