from datetime import timedelta
from typing import Callable

from app.gpt.prompt import (
    MERGE_PROMPT,
    POLISHED_TRANSCRIPT_CHUNK_PROMPT,
    POLISHED_TRANSCRIPT_MERGE_PROMPT,
    POLISHED_TRANSCRIPT_PROMPT,
    POLISHED_TRANSCRIPT_REPAIR_PROMPT,
)
from app.gpt.prompt_builder import generate_base_prompt


def format_time(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))[2:]


def build_segment_text(segments: list, format_time_func: Callable[[float], str] = format_time) -> str:
    return "\n".join(
        f"{format_time_func(seg.start)} - {seg.text.strip()}"
        for seg in segments
    )


def build_text_message(text: str) -> list:
    return [{
        "role": "user",
        "content": [{"type": "text", "text": text}]
    }]


def build_note_messages(
    *,
    segment_text: str,
    title=None,
    tags=None,
    _format=None,
    style=None,
    extras=None,
    video_img_urls=(),
    generate_prompt=generate_base_prompt,
) -> list:
    content_text = generate_prompt(
        title=title,
        segment_text=segment_text,
        tags=tags,
        _format=_format,
        style=style,
        extras=extras,
    )

    content: list[dict] = [{"type": "text", "text": content_text}]
    for url in video_img_urls:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": url,
                "detail": "auto"
            }
        })

    return [{
        "role": "user",
        "content": content
    }]


def build_merge_messages(partials: list, merge_prompt: str = MERGE_PROMPT) -> list:
    merge_text = merge_prompt + "\n\n" + "\n\n---\n\n".join(partials)
    return build_text_message(merge_text)


def build_polished_transcript_messages(
    *,
    segment_text: str,
    title=None,
    tags=None,
    section_guidance: str,
    language_guidance: str,
    prompt_template: str = POLISHED_TRANSCRIPT_PROMPT,
) -> list:
    prompt = prompt_template.format(
        video_title=title,
        segment_text=segment_text,
        tags=tags,
        section_guidance=section_guidance,
        language_guidance=language_guidance,
    )
    return build_text_message(prompt)


def build_polished_transcript_chunk_messages(
    *,
    segment_text: str,
    title=None,
    tags=None,
    language_guidance: str,
    prompt_template: str = POLISHED_TRANSCRIPT_CHUNK_PROMPT,
) -> list:
    prompt = prompt_template.format(
        video_title=title,
        segment_text=segment_text,
        tags=tags,
        language_guidance=language_guidance,
    )
    return build_text_message(prompt)


def build_polished_transcript_merge_messages(
    partials: list,
    language_guidance: str,
    prompt_template: str = POLISHED_TRANSCRIPT_MERGE_PROMPT,
) -> list:
    merge_text = (
        prompt_template.format(language_guidance=language_guidance)
        + "\n\n"
        + "\n\n---\n\n".join(partials)
    )
    return build_text_message(merge_text)


def build_polished_transcript_repair_messages(
    *,
    segment_text: str,
    draft_text: str,
    title=None,
    tags=None,
    language_guidance: str,
    prompt_template: str = POLISHED_TRANSCRIPT_REPAIR_PROMPT,
) -> list:
    prompt = prompt_template.format(
        video_title=title,
        segment_text=segment_text,
        tags=tags,
        draft_text=draft_text,
        language_guidance=language_guidance,
    )
    return build_text_message(prompt)


def summarize_messages(messages: list) -> str:
    parts = []
    for message in messages:
        role = message.get("role", "unknown")
        content = message.get("content")
        if isinstance(content, list):
            text_chars = sum(
                len(item.get("text", ""))
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            )
            image_count = sum(
                1
                for item in content
                if isinstance(item, dict) and item.get("type") == "image_url"
            )
            parts.append(f"{role}:parts={len(content)},text_chars={text_chars},images={image_count}")
        elif isinstance(content, str):
            parts.append(f"{role}:chars={len(content)}")
        else:
            parts.append(f"{role}:type={type(content).__name__}")
    return "; ".join(parts)
