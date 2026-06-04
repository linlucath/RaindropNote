from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse


def infer_platform_from_url(url: str) -> Optional[str]:
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in ("http", "https"):
        return None

    host = parsed.netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "bilibili.com" in host or "b23.tv" in host:
        return "bilibili"
    if "douyin.com" in host:
        return "douyin"
    if "kuaishou.com" in host:
        return "kuaishou"

    return None


def extract_video_id_from_url(url: str, platform: str) -> Optional[str]:
    if platform == "bilibili":
        match = re.search(r"BV([0-9A-Za-z]+)", url)
        return f"BV{match.group(1)}" if match else None

    if platform == "youtube":
        match = re.search(r"(?:v=|youtu\.be/)([0-9A-Za-z_-]{11})", url)
        return match.group(1) if match else None

    if platform == "douyin":
        match = re.search(r"/video/(\d+)", url)
        return match.group(1) if match else None

    return None
