from typing import List


def _segment_text(segment) -> str:
    return (getattr(segment, "text", "") or "").strip()


def source_text_length(segments: list) -> int:
    return sum(len(_segment_text(segment)) for segment in segments)


def polished_transcript_section_guidance(segments: list) -> str:
    text_length = source_text_length(segments)
    if text_length >= 12000:
        return "6-12 个 `##` 章节"
    if text_length >= 5000:
        return "4-8 个 `##` 章节"
    return "3-6 个 `##` 章节"


def polished_transcript_language_guidance(language: str | None, segments: list) -> str:
    normalized_language = (language or "").lower()
    if normalized_language.startswith("zh"):
        return "如果原字幕本身是中文，就按现有方式输出自然、完整的简体中文文字稿，不需要双语对照。 "

    sample_text = " ".join(_segment_text(segment) for segment in segments[:5]).strip()
    has_chinese = any("\u4e00" <= char <= "\u9fff" for char in sample_text)
    if not normalized_language and has_chinese:
        return "如果原字幕本身是中文，就按现有方式输出自然、完整的简体中文文字稿，不需要双语对照。 "

    return (
        "如果原字幕主体不是中文，请输出双语文字稿：先输出英文原段落，下一自然段紧跟对应的中文翻译；"
        "保持一段英文、一段中文交替出现，不要把英文和中文写在同一段里，也不要只保留中文摘要。"
        "直接从正文开始，不要添加任何导语、编者按、说明信息或标签；"
        "不要写“以下是整理后的双语文字稿”“英文原文：”“中文翻译：”之类的字样。"
    )


def strip_markdown_for_length(text: str) -> str:
    cleaned = text or ""
    replacements = (
        ("**", ""),
        ("### ", ""),
        ("## ", ""),
        ("# ", ""),
        ("`", ""),
        ("> ", ""),
        ("-", " "),
        ("*", ""),
    )
    for old, new in replacements:
        cleaned = cleaned.replace(old, new)
    return " ".join(cleaned.split())


def needs_polished_transcript_repair(segments: list, draft_text: str) -> bool:
    source_length = source_text_length(segments)
    if source_length <= 0:
        return False

    output_length = len(strip_markdown_for_length(draft_text))
    ratio = output_length / source_length
    threshold = 0.72 if source_length < 12000 else 0.82
    return ratio < threshold


def split_polished_transcript_segments(
    segments: list,
    max_source_chars: int,
    chunker,
    *,
    title: str,
    tags,
) -> list:
    budget = max(500, max_source_chars)
    coarse_groups: List[list] = []
    current_group: list = []
    current_chars = 0

    for segment in segments:
        segment_chars = len(_segment_text(segment))

        if current_group and current_chars + segment_chars > budget:
            coarse_groups.append(current_group)
            current_group = []
            current_chars = 0

        current_group.append(segment)
        current_chars += segment_chars

    if current_group:
        coarse_groups.append(current_group)

    chunks = []
    for group in coarse_groups:
        chunks.extend(chunker.chunk(group, [], title=title, tags=tags))
    return chunks


def stitch_polished_transcript_partials(partials: list[str]) -> str:
    cleaned = [part.strip() for part in partials if part and part.strip()]
    if not cleaned:
        return ""
    stitched = "\n\n".join(cleaned)
    stitched = stitched.replace("\r\n", "\n")
    while "\n\n\n" in stitched:
        stitched = stitched.replace("\n\n\n", "\n\n")
    return stitched.strip()
