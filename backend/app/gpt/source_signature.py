import hashlib
import json


def build_source_signature(
    source,
    *,
    model: str,
    temperature: float,
    max_request_bytes: int,
) -> str:
    payload = {
        "model": model,
        "temperature": temperature,
        "max_request_bytes": max_request_bytes,
        "title": source.title,
        "tags": source.tags,
        "format": source._format,
        "style": source.style,
        "extras": source.extras,
        "video_img_urls": source.video_img_urls or [],
        "segments": [
            {
                "start": getattr(seg, "start", None),
                "end": getattr(seg, "end", None),
                "text": getattr(seg, "text", ""),
            }
            for seg in source.segment
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
