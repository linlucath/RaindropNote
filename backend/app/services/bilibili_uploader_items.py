from __future__ import annotations

from typing import Any


def normalize_uploader_video_item(item: dict[str, Any]) -> dict[str, str] | None:
    bvid = str(item.get('bvid') or '').strip()
    if not bvid:
        return None

    jump_url = str(item.get('jump_url') or '').strip()
    if jump_url.startswith('//'):
        video_url = f'https:{jump_url}'
    elif jump_url.startswith('http://') or jump_url.startswith('https://'):
        video_url = jump_url
    else:
        video_url = f'https://www.bilibili.com/video/{bvid}'

    return {
        'video_id': bvid,
        'video_url': video_url,
        'title': str(item.get('title') or '').strip(),
        'view_count': int(item.get('play') or 0),
    }
