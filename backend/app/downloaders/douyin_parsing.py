import re
from typing import Any


DOUYIN_URL_RE = (
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|"
    r"(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)


def find_urls(text: str) -> list[str]:
    return re.findall(DOUYIN_URL_RE, text)


def extract_aweme_id(url: str) -> str:
    patterns = [
        r"video/(\d+)",
        r"aweme_id=(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


def parse_audio_metadata(video_data: dict[str, Any]) -> dict[str, Any]:
    aweme_detail = video_data["aweme_detail"]
    video = aweme_detail["video"]
    tags = []
    for tag in aweme_detail["video_tag"]:
        if tag["tag_name"]:
            tags.append(tag["tag_name"])

    return {
        "audio_url": aweme_detail["music"]["play_url"]["uri"],
        "cover_url": (
            video["cover_original_scale"]["url_list"][0]
            if video["cover"]
            else video_data["video"]["big_thumbs"]["img_url"]
        ),
        "duration": video["duration"],
        "raw_tags": aweme_detail["caption"] + "".join(tags),
        "title": aweme_detail["item_title"],
        "video_id": aweme_detail["aweme_id"],
    }


def parse_video_download_metadata(video_data: dict[str, Any]) -> dict[str, str]:
    aweme_detail = video_data["aweme_detail"]
    return {
        "download_url": aweme_detail["video"]["download_addr"]["url_list"][0],
        "video_id": aweme_detail["aweme_id"],
    }
