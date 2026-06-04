import json
import tempfile
import unittest
from pathlib import Path

from app.services.favorite_notes import load_favorite_note


class TestFavoriteNotes(unittest.TestCase):
    def test_load_favorite_note_reads_task_json_and_builds_favorite_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "task-1.json").write_text(
                json.dumps(
                    {
                        "markdown": "# 测试视频\n\n正文",
                        "transcript": {"full_text": "正文", "segments": []},
                        "audio_meta": {
                            "title": "测试视频",
                            "video_id": "BVfavorite",
                            "platform": "bilibili",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            note = load_favorite_note("task-1", output_dir)

        self.assertIsNotNone(note)
        self.assertEqual(note["title"], "测试视频")
        self.assertEqual(note["video_id"], "BVfavorite")
        self.assertEqual(note["platform"], "bilibili")
        self.assertEqual(note["markdown"], "# 测试视频\n\n正文")
        self.assertEqual(note["content"], "# 测试视频\n\n正文")
        self.assertEqual(note["transcript"], {"full_text": "正文", "segments": []})
        self.assertEqual(
            note["audio_meta"],
            {
                "title": "测试视频",
                "video_id": "BVfavorite",
                "platform": "bilibili",
            },
        )

    def test_load_favorite_note_supports_camel_case_audio_meta_and_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "task-2.json").write_text(
                json.dumps(
                    {
                        "audioMeta": {
                            "video_id": "yt-1",
                            "platform": "youtube",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            note = load_favorite_note("task-2", str(output_dir))

        self.assertIsNotNone(note)
        self.assertEqual(note["title"], "未命名文字稿")
        self.assertEqual(note["video_id"], "yt-1")
        self.assertEqual(note["platform"], "youtube")
        self.assertEqual(note["markdown"], "")
        self.assertEqual(note["content"], "")
        self.assertIsNone(note["transcript"])
        self.assertEqual(note["audio_meta"], {"video_id": "yt-1", "platform": "youtube"})

    def test_load_favorite_note_returns_none_for_missing_or_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "bad-json.json").write_text("{not-json", encoding="utf-8")

            missing_note = load_favorite_note("missing", output_dir)
            bad_json_note = load_favorite_note("bad-json", output_dir)

        self.assertIsNone(missing_note)
        self.assertIsNone(bad_json_note)


if __name__ == "__main__":
    unittest.main()
