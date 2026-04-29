import unittest
from unittest.mock import Mock

from app.gpt.prompt import POLISHED_TRANSCRIPT_MERGE_PROMPT, POLISHED_TRANSCRIPT_PROMPT
from app.gpt.universal_gpt import UniversalGPT
from app.models.gpt_model import GPTSource
from app.models.transcriber_model import TranscriptSegment


class TestPolishedTranscriptPrompt(unittest.TestCase):
    def test_prompt_requires_reading_structure_without_timestamps(self):
        self.assertIn("## 阅读导览", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("4-8 个 `##` 章节", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("关键判断句做少量加粗", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("不要输出时间戳", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("不要改成要点清单", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("不应低于原始转写正文的 70%", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("“磁机素”应校正为“雌激素”", POLISHED_TRANSCRIPT_PROMPT)

    def test_merge_prompt_keeps_single_reading_guide(self):
        self.assertIn("只保留开头一个 `## 阅读导览`", POLISHED_TRANSCRIPT_MERGE_PROMPT)
        self.assertIn("4-8 个有信息量的 `##` 章节", POLISHED_TRANSCRIPT_MERGE_PROMPT)
        self.assertIn("不要压缩信息量", POLISHED_TRANSCRIPT_MERGE_PROMPT)

    def test_polished_transcript_merges_multiple_chunks(self):
        gpt = UniversalGPT(client=Mock(), model="demo")
        gpt.max_request_bytes = 3800

        def fake_completion(messages):
            text = messages[0]["content"][0]["text"]
            if "你将收到多个来自同一视频的校对文字稿片段" in text:
                content = "## 阅读导览\n\n合并导览。\n\n## 第一章\n\n正文一。\n\n## 第二章\n\n正文二。"
            else:
                content = "## 阅读导览\n\n片段导览。\n\n## 片段章节\n\n片段正文。"
            return Mock(choices=[Mock(message=Mock(content=content))])

        gpt._chat_completion_create = Mock(side_effect=fake_completion)

        source = GPTSource(
            title="测试",
            tags=[],
            segment=[
                TranscriptSegment(start=0, end=1, text="甲" * 1200),
                TranscriptSegment(start=1, end=2, text="乙" * 1200),
            ],
        )

        result = gpt.polish_transcript(source)

        self.assertIn("## 阅读导览", result)
        self.assertIn("## 第一章", result)
        self.assertIn("## 第二章", result)
        self.assertGreater(gpt._chat_completion_create.call_count, 1)


if __name__ == "__main__":
    unittest.main()
