import unittest
from unittest.mock import Mock

from app.gpt.prompt import (
    POLISHED_TRANSCRIPT_CHUNK_PROMPT,
    POLISHED_TRANSCRIPT_MERGE_PROMPT,
    POLISHED_TRANSCRIPT_PROMPT,
    POLISHED_TRANSCRIPT_REPAIR_PROMPT,
)
from app.gpt.universal_gpt import UniversalGPT
from app.models.gpt_model import GPTSource
from app.models.transcriber_model import TranscriptSegment


class TestPolishedTranscriptPrompt(unittest.TestCase):
    def test_prompt_requires_reading_structure_without_timestamps(self):
        self.assertIn("## 阅读导览", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("{section_guidance}", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("关键判断句做少量加粗", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("不要输出时间戳", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("不要改成要点清单", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("不应低于原始转写正文的 70%", POLISHED_TRANSCRIPT_PROMPT)
        self.assertIn("“磁机素”应校正为“雌激素”", POLISHED_TRANSCRIPT_PROMPT)

    def test_merge_prompt_keeps_single_reading_guide(self):
        self.assertIn("只保留开头一个 `## 阅读导览`", POLISHED_TRANSCRIPT_MERGE_PROMPT)
        self.assertIn("4-8 个有信息量的 `##` 章节", POLISHED_TRANSCRIPT_MERGE_PROMPT)
        self.assertIn("不要压缩信息量", POLISHED_TRANSCRIPT_MERGE_PROMPT)

    def test_chunk_prompt_outputs_body_only(self):
        self.assertIn("不要输出任何标题", POLISHED_TRANSCRIPT_CHUNK_PROMPT)
        self.assertIn("不要输出 `## 阅读导览`", POLISHED_TRANSCRIPT_CHUNK_PROMPT)
        self.assertIn("只返回这一段对应的正文", POLISHED_TRANSCRIPT_CHUNK_PROMPT)

    def test_repair_prompt_requires_restoring_missing_details(self):
        self.assertIn("补回被遗漏的事实", POLISHED_TRANSCRIPT_REPAIR_PROMPT)
        self.assertIn("不要把它写成文章", POLISHED_TRANSCRIPT_REPAIR_PROMPT)
        self.assertIn("按原视频的展开顺序", POLISHED_TRANSCRIPT_REPAIR_PROMPT)

    def test_long_transcript_prompt_uses_more_sections_and_less_commentary(self):
        gpt = UniversalGPT(client=Mock(), model="demo")
        messages = gpt._build_polished_transcript_messages(
            [
                TranscriptSegment(start=0, end=1, text="甲" * 7000),
                TranscriptSegment(start=1, end=2, text="乙" * 7000),
            ],
            title="长视频",
            tags=[],
        )

        prompt = messages[0]["content"][0]["text"]
        self.assertIn("6-12 个 `##` 章节", prompt)
        self.assertIn("不要另写总结式结尾", prompt)
        self.assertIn("不要把它重新组织成议论文", prompt)

    def test_non_chinese_polished_transcript_prompt_requires_bilingual_paragraph_pairs(self):
        gpt = UniversalGPT(client=Mock(), model="demo")
        messages = gpt._build_polished_transcript_messages(
            [TranscriptSegment(start=0, end=1, text="hello world")],
            title="English video",
            tags=[],
            language="en",
        )

        prompt = messages[0]["content"][0]["text"]
        self.assertIn("先输出英文原段落", prompt)
        self.assertIn("下一自然段紧跟对应的中文翻译", prompt)
        self.assertIn("不要把英文和中文写在同一段里", prompt)
        self.assertIn("不要添加任何导语、编者按、说明信息或标签", prompt)

    def test_chinese_polished_transcript_prompt_does_not_require_bilingual_output(self):
        gpt = UniversalGPT(client=Mock(), model="demo")
        messages = gpt._build_polished_transcript_messages(
            [TranscriptSegment(start=0, end=1, text="你好，世界")],
            title="中文视频",
            tags=[],
            language="zh",
        )

        prompt = messages[0]["content"][0]["text"]
        self.assertNotIn("先输出英文原段落", prompt)

    def test_polished_transcript_stitches_multiple_chunks_without_merge_prompt(self):
        gpt = UniversalGPT(client=Mock(), model="demo")
        gpt.max_request_bytes = 2500

        def fake_completion(messages):
            text = messages[0]["content"][0]["text"]
            if "请你修复下面这份校对文字稿" in text:
                content = "第一段正文。\n\n第二段正文。"
            else:
                marker = "第一段正文。" if "甲" in text else "第二段正文。"
                content = marker
            return Mock(choices=[Mock(message=Mock(content=content))])

        gpt._chat_completion_create = Mock(side_effect=fake_completion)

        source = GPTSource(
            title="测试",
            tags=[],
            segment=[
                TranscriptSegment(start=0, end=1, text="甲" * 1800),
                TranscriptSegment(start=1, end=2, text="乙" * 1800),
            ],
        )

        result = gpt.polish_transcript(source)

        self.assertIn("第一段正文。", result)
        self.assertIn("第二段正文。", result)
        self.assertNotIn("你将收到多个来自同一视频的校对文字稿片段", str(gpt._chat_completion_create.call_args_list))
        self.assertGreater(gpt._chat_completion_create.call_count, 1)

    def test_polished_transcript_splits_by_source_length_even_when_request_is_small_enough(self):
        gpt = UniversalGPT(client=Mock(), model="demo")
        gpt.max_request_bytes = 10**9
        gpt.polished_transcript_max_source_chars = 2500

        def fake_completion(messages):
            text = messages[0]["content"][0]["text"]
            marker = "第一块。" if "甲" in text else "第二块。"
            return Mock(choices=[Mock(message=Mock(content=marker))])

        gpt._chat_completion_create = Mock(side_effect=fake_completion)

        source = GPTSource(
            title="测试",
            tags=[],
            segment=[
                TranscriptSegment(start=0, end=1, text="甲" * 1800),
                TranscriptSegment(start=1, end=2, text="乙" * 1800),
            ],
        )

        result = gpt.polish_transcript(source)

        self.assertIn("第一块。", result)
        self.assertIn("第二块。", result)
        self.assertGreaterEqual(gpt._chat_completion_create.call_count, 2)

    def test_polished_transcript_repairs_overcompressed_draft(self):
        gpt = UniversalGPT(client=Mock(), model="demo")
        source = GPTSource(
            title="测试",
            tags=[],
            segment=[
                TranscriptSegment(start=0, end=1, text="第一段信息" * 400),
                TranscriptSegment(start=1, end=2, text="第二段案例" * 400),
            ],
        )

        def fake_completion(messages):
            text = messages[0]["content"][0]["text"]
            if "请你修复下面这份校对文字稿" in text:
                return Mock(choices=[Mock(message=Mock(content=(
                    "## 阅读导览\n\n这是一份修复后的文字稿。\n\n"
                    "## 第一部分\n\n" + ("第一段信息" * 200) + "\n\n"
                    "## 第二部分\n\n" + ("第二段案例" * 200)
                )))])
            return Mock(choices=[Mock(message=Mock(content="## 阅读导览\n\n简述。\n\n## 第一部分\n\n过短。"))])

        gpt._chat_completion_create = Mock(side_effect=fake_completion)

        result = gpt.polish_transcript(source)

        self.assertIn("修复后的文字稿", result)
        self.assertGreaterEqual(gpt._chat_completion_create.call_count, 2)


if __name__ == "__main__":
    unittest.main()
