import unittest

from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.services import transcript_markdown


class TestTranscriptMarkdown(unittest.TestCase):
    def test_builds_readable_simplified_transcript_markdown(self):
        audio_meta = AudioDownloadResult(
            file_path="/tmp/demo.mp3",
            title="測試視頻",
            duration=30,
            cover_url=None,
            platform="bilibili",
            video_id="BV123",
            raw_info={"webpage_url": "https://www.bilibili.com/video/BV123"},
        )
        transcript = TranscriptResult(
            language="zh",
            full_text="這個視頻講學習。後面還補充了一個觀點。",
            segments=[
                TranscriptSegment(start=3, end=8, text="這個視頻講學習。"),
                TranscriptSegment(start=12, end=18, text="後面還補充了一個觀點。"),
            ],
        )

        markdown = transcript_markdown.build_transcript_markdown(audio_meta, transcript)

        self.assertIn("# 测试视频", markdown)
        self.assertIn("## 简体中文文字稿", markdown)
        self.assertIn("这个视频讲学习。后面还补充了一个观点。", markdown)
        self.assertIn("## 带时间戳文字稿", markdown)
        self.assertIn("[00:03] 这个视频讲学习。", markdown)
        self.assertIn("[00:12] 后面还补充了一个观点。", markdown)


if __name__ == "__main__":
    unittest.main()
