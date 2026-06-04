import re

from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult


def format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds or 0)
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def simplify_chinese(text: str) -> str:
    if not text:
        return ""

    try:
        from opencc import OpenCC
        return OpenCC("t2s").convert(text)
    except Exception:
        phrase_map = {
            "視頻": "视频",
        }
        for source, target in phrase_map.items():
            text = text.replace(source, target)
        fallback_map = str.maketrans({
            "這": "这", "個": "个", "視": "视", "頻": "频",
            "學": "学", "習": "习", "後": "后", "還": "还", "補": "补",
            "觀": "观", "點": "点", "測": "测", "試": "试", "裏": "里",
            "裡": "里", "與": "与", "為": "为", "會": "会", "說": "说",
            "講": "讲", "讓": "让", "對": "对", "開": "开", "關": "关",
            "題": "题", "體": "体", "現": "现", "實": "实", "應": "应",
            "產": "产", "業": "业", "經": "经", "營": "营", "專": "专",
            "區": "区", "並": "并", "從": "从", "變": "变", "種": "种",
            "時": "时", "間": "间", "線": "线", "錄": "录", "轉": "转",
            "寫": "写", "長": "长", "標": "标", "簡": "简", "體": "体",
        })
        return text.translate(fallback_map)


def normalize_transcript_text(text: str) -> str:
    simplified = simplify_chinese(text.strip())
    simplified = re.sub(r"\s+", " ", simplified)
    simplified = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", simplified)
    return simplified


def build_transcript_markdown(audio_meta: AudioDownloadResult, transcript: TranscriptResult) -> str:
    title = normalize_transcript_text(audio_meta.title or "未命名视频")
    segment_texts = [
        normalize_transcript_text(segment.text)
        for segment in transcript.segments
        if segment.text and segment.text.strip()
    ]
    readable_text = normalize_transcript_text("".join(segment_texts))
    timestamp_lines = [
        f"[{format_timestamp(segment.start)}] {normalize_transcript_text(segment.text)}"
        for segment in transcript.segments
        if segment.text and segment.text.strip()
    ]

    return "\n\n".join([
        f"# {title}",
        "## 简体中文文字稿",
        readable_text or normalize_transcript_text(transcript.full_text or ""),
        "## 带时间戳文字稿",
        "\n".join(timestamp_lines),
    ]).strip()
