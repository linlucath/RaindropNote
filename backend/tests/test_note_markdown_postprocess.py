import unittest
from pathlib import Path
from unittest.mock import Mock

from app.models.audio_model import AudioDownloadResult
from app.services import note_markdown_postprocess


def _audio_meta(platform: str = "bilibili") -> AudioDownloadResult:
    return AudioDownloadResult(
        file_path="/tmp/demo.mp3",
        title="Demo",
        duration=120,
        cover_url=None,
        platform=platform,
        video_id="BV123",
        raw_info={},
    )


class TestNoteMarkdownPostprocess(unittest.TestCase):
    def test_insert_screenshots_replaces_markers_with_generated_image_urls(self):
        generate_screenshot = Mock(side_effect=[
            "/tmp/screenshots/first.jpg",
            "/tmp/screenshots/second.jpg",
        ])

        markdown = note_markdown_postprocess.insert_screenshots(
            "A *Screenshot-[01:02]\nB Screenshot-03:04",
            video_path=Path("/tmp/video.mp4"),
            image_output_dir="/tmp/screenshots",
            image_base_url="/static/screenshots",
            generate_screenshot=generate_screenshot,
        )

        self.assertEqual(markdown, "A ![](/static/screenshots/first.jpg)\nB ![](/static/screenshots/second.jpg)")
        self.assertEqual(generate_screenshot.call_args_list[0].args, (
            "/tmp/video.mp4",
            "/tmp/screenshots",
            62,
            0,
        ))
        self.assertEqual(generate_screenshot.call_args_list[1].args[2], 184)

    def test_insert_screenshots_uses_runtime_generate_screenshot_patch_by_default(self):
        with unittest.mock.patch(
            "app.services.note_markdown_postprocess.default_generate_screenshot",
            return_value="/tmp/screenshots/runtime.jpg",
        ) as generate_screenshot:
            markdown = note_markdown_postprocess.insert_screenshots(
                "A *Screenshot-[01:02]",
                video_path=Path("/tmp/video.mp4"),
                image_output_dir="/tmp/screenshots",
                image_base_url="/static/screenshots",
            )

        self.assertEqual(markdown, "A ![](/static/screenshots/runtime.jpg)")
        generate_screenshot.assert_called_once_with(
            "/tmp/video.mp4",
            "/tmp/screenshots",
            62,
            0,
        )

    def test_insert_screenshots_returns_none_when_generation_fails(self):
        markdown = note_markdown_postprocess.insert_screenshots(
            "A *Screenshot-[01:02]",
            video_path=Path("/tmp/video.mp4"),
            image_output_dir="/tmp/screenshots",
            image_base_url="/static/screenshots",
            generate_screenshot=Mock(side_effect=RuntimeError("ffmpeg failed")),
        )

        self.assertIsNone(markdown)

    def test_post_process_markdown_applies_screenshots_and_links_when_requested(self):
        markdown = note_markdown_postprocess.post_process_markdown(
            markdown="A *Screenshot-[01:02]\nB Content-[03:04]",
            video_path=Path("/tmp/video.mp4"),
            formats=["screenshot", "link"],
            audio_meta=_audio_meta(),
            platform="bilibili",
            insert_screenshots=lambda markdown, video_path: markdown.replace(
                "*Screenshot-[01:02]",
                "![](/static/screenshots/first.jpg)",
            ),
        )

        self.assertIn("![](/static/screenshots/first.jpg)", markdown)
        self.assertIn("[原片 @ 03:04](https://www.bilibili.com/video/BV123&t=184)", markdown)

    def test_post_process_markdown_skips_screenshot_when_video_path_missing(self):
        insert_screenshots = Mock(side_effect=AssertionError("should not insert screenshots"))

        markdown = note_markdown_postprocess.post_process_markdown(
            markdown="A *Screenshot-[01:02]\nB Content-[03:04]",
            video_path=None,
            formats=["screenshot", "link"],
            audio_meta=_audio_meta("youtube"),
            platform="youtube",
            insert_screenshots=insert_screenshots,
        )

        self.assertNotIn("![](", markdown)
        self.assertIn("[原片 @ 03:04](https://www.youtube.com/watch?v=BV123&t=184s)", markdown)
        insert_screenshots.assert_not_called()


if __name__ == "__main__":
    unittest.main()
