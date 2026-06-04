from app.gpt.legacy_messages import (
    build_legacy_prompt_messages,
    build_segment_text,
    ensure_segments_type,
    format_time,
)
from app.models.transcriber_model import TranscriptSegment


def test_format_time_and_segment_text_keep_legacy_shape():
    segments = [
        TranscriptSegment(start=3, end=5, text=" first "),
        TranscriptSegment(start=65, end=70, text="second"),
    ]

    assert format_time(3) == "00:03"
    assert format_time(65) == "01:05"
    assert build_segment_text(segments) == "00:03 - first\n01:05 - second"


def test_ensure_segments_type_converts_dicts_without_touching_segment_instances():
    existing = TranscriptSegment(start=3, end=5, text="existing")
    result = ensure_segments_type([
        {"start": 1, "end": 2, "text": "from dict"},
        existing,
    ])

    assert result[0].text == "from dict"
    assert result[1] is existing


def test_build_legacy_prompt_messages_appends_optional_screenshot_and_link_prompts():
    messages = build_legacy_prompt_messages(
        [TranscriptSegment(start=3, end=5, text="demo transcript")],
        title="Demo title",
        tags="demo-tag",
        include_screenshot=True,
        include_link=True,
    )

    assert messages[0]["role"] == "user"
    assert "Demo title" in messages[0]["content"]
    assert "demo transcript" in messages[0]["content"]
    assert "demo-tag" in messages[0]["content"]
    assert "Screenshot" in messages[0]["content"]
    assert "Content" in messages[0]["content"]
