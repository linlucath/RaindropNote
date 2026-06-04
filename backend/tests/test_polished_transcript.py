from types import SimpleNamespace

from app.gpt.polished_transcript import (
    needs_polished_transcript_repair,
    polished_transcript_language_guidance,
    polished_transcript_section_guidance,
    stitch_polished_transcript_partials,
)


def _segment(text: str):
    return SimpleNamespace(text=text)


def test_section_guidance_uses_source_length_thresholds():
    assert polished_transcript_section_guidance([_segment("甲" * 4999)]) == "3-6 个 `##` 章节"
    assert polished_transcript_section_guidance([_segment("甲" * 5000)]) == "4-8 个 `##` 章节"
    assert polished_transcript_section_guidance([_segment("甲" * 11999)]) == "4-8 个 `##` 章节"
    assert polished_transcript_section_guidance([_segment("甲" * 12000)]) == "6-12 个 `##` 章节"


def test_language_guidance_treats_chinese_language_or_sample_as_chinese():
    explicit_chinese = polished_transcript_language_guidance("zh-CN", [_segment("hello")])
    inferred_chinese = polished_transcript_language_guidance(None, [_segment("你好，世界")])

    assert "不需要双语对照" in explicit_chinese
    assert "不需要双语对照" in inferred_chinese
    assert "先输出英文原段落" not in explicit_chinese
    assert "先输出英文原段落" not in inferred_chinese


def test_language_guidance_requires_bilingual_output_for_non_chinese_source():
    guidance = polished_transcript_language_guidance("en", [_segment("hello world")])

    assert "先输出英文原段落" in guidance
    assert "下一自然段紧跟对应的中文翻译" in guidance
    assert "不要把英文和中文写在同一段里" in guidance


def test_repair_ratio_threshold_is_72_percent_for_short_sources():
    segments = [_segment("甲" * 100)]

    assert needs_polished_transcript_repair(segments, "乙" * 71) is True
    assert needs_polished_transcript_repair(segments, "乙" * 72) is False


def test_repair_ratio_threshold_is_82_percent_for_long_sources():
    segments = [_segment("甲" * 12000)]

    assert needs_polished_transcript_repair(segments, "乙" * 9839) is True
    assert needs_polished_transcript_repair(segments, "乙" * 9840) is False


def test_stitch_partials_removes_empty_parts_and_compresses_blank_lines():
    result = stitch_polished_transcript_partials(
        [
            "  第一段。\n\n\n第二段。  ",
            "",
            "   ",
            "\n\n第三段。\r\n\r\n\r\n第四段。\n",
        ]
    )

    assert result == "第一段。\n\n第二段。\n\n第三段。\n\n第四段。"
