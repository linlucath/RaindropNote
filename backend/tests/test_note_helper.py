import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "utils" / "note_helper.py"
spec = importlib.util.spec_from_file_location("note_helper", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("note_helper module spec not found")
note_helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(note_helper)


class TestNoteHelper(unittest.TestCase):
    def test_prepend_source_link_adds_header_at_top(self):
        source_url = "https://www.bilibili.com/video/BV1xx411c7mD"
        markdown = "## 标题\n\n内容"

        result = note_helper.prepend_source_link(markdown, source_url)

        self.assertTrue(result.startswith(f"> 来源链接：{source_url}\n\n"))
        self.assertIn("## 标题", result)

    def test_prepend_source_link_does_not_duplicate_when_header_exists(self):
        source_url = "https://www.youtube.com/watch?v=abc123"
        markdown = f"> 来源链接：{source_url}\n\n## 标题\n\n内容"

        result = note_helper.prepend_source_link(markdown, source_url)

        self.assertEqual(result, markdown)

    def test_replace_content_markers_builds_bilibili_timestamp_link(self):
        markdown = "## 章节 Content-[04:16]"

        result = note_helper.replace_content_markers(markdown, "BV123_p2", "bilibili")

        self.assertEqual(
            result,
            "## 章节 [原片 @ 04:16](https://www.bilibili.com/video/BV123?p=2&t=256)",
        )

    def test_replace_content_markers_builds_youtube_timestamp_link(self):
        markdown = "## Chapter Content-[01:05]"

        result = note_helper.replace_content_markers(markdown, "abc123", "youtube")

        self.assertEqual(
            result,
            "## Chapter [原片 @ 01:05](https://www.youtube.com/watch?v=abc123&t=65s)",
        )


if __name__ == "__main__":
    unittest.main()
