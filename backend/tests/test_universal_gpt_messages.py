from unittest.mock import Mock

from app.gpt.message_payloads import (
    build_merge_messages,
    build_note_messages,
    build_segment_text,
    summarize_messages,
)
from app.gpt.prompt import MERGE_PROMPT
from app.gpt.universal_gpt import UniversalGPT
from app.models.transcriber_model import TranscriptSegment


def test_build_segment_text_formats_times_and_strips_text():
    segments = [
        TranscriptSegment(start=65.8, end=70, text="  第一段  "),
        TranscriptSegment(start=3661.2, end=3662, text="第二段"),
    ]

    assert build_segment_text(segments) == "01:05 - 第一段\n01:01 - 第二段"


def test_build_note_messages_keeps_text_and_images_in_one_user_message():
    messages = build_note_messages(
        segment_text="00:01 - hello",
        title="视频标题",
        tags=["tag-a"],
        _format=["toc"],
        style="minimal",
        extras="额外要求",
        video_img_urls=["https://example.com/a.jpg", "https://example.com/b.jpg"],
    )

    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert content[0]["type"] == "text"
    assert "视频标题" in content[0]["text"]
    assert "00:01 - hello" in content[0]["text"]
    assert "额外要求" in content[0]["text"]
    assert content[1:] == [
        {"type": "image_url", "image_url": {"url": "https://example.com/a.jpg", "detail": "auto"}},
        {"type": "image_url", "image_url": {"url": "https://example.com/b.jpg", "detail": "auto"}},
    ]


def test_build_merge_messages_wraps_partials_with_legacy_separator():
    messages = build_merge_messages(["part-a", "part-b"])

    assert messages == [
        {
            "role": "user",
            "content": [{"type": "text", "text": MERGE_PROMPT + "\n\npart-a\n\n---\n\npart-b"}],
        }
    ]


def test_summarize_messages_describes_multimodal_and_plain_content():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "abc"},
                {"type": "image_url", "image_url": {"url": "https://example.com/a.jpg"}},
                {"type": "text", "text": "中文"},
            ],
        },
        {"role": "system", "content": "plain"},
        {"role": "assistant", "content": None},
    ]

    assert (
        summarize_messages(messages)
        == "user:parts=3,text_chars=5,images=1; system:chars=5; assistant:type=NoneType"
    )


def test_universal_gpt_keeps_legacy_private_wrappers():
    gpt = UniversalGPT(client=Mock(), model="demo-model")
    segments = [TranscriptSegment(start=1, end=2, text=" hello ")]

    assert gpt._build_segment_text(segments) == build_segment_text(segments)
    assert gpt._build_merge_messages(["a", "b"]) == build_merge_messages(["a", "b"])
    assert gpt._summarize_messages([{"role": "user", "content": "abc"}]) == "user:chars=3"


def test_create_messages_still_respects_monkeypatched_segment_text_wrapper():
    gpt = UniversalGPT(client=Mock(), model="demo-model")
    gpt._build_segment_text = Mock(return_value="patched segment text")

    messages = gpt.create_messages(
        [TranscriptSegment(start=1, end=2, text="original text")],
        title="标题",
        tags=[],
    )

    gpt._build_segment_text.assert_called_once()
    assert "patched segment text" in messages[0]["content"][0]["text"]
    assert "original text" not in messages[0]["content"][0]["text"]
