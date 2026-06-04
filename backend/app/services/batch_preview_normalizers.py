def normalize_bilibili_entries(entries: list[dict]) -> list[dict]:
    videos = []
    seen = set()
    for entry in entries:
        video_id = entry.get("id") or entry.get("bvid")
        if not video_id or not str(video_id).startswith("BV") or video_id in seen:
            continue
        seen.add(video_id)
        videos.append({
            "video_id": video_id,
            "video_url": entry.get("url") or entry.get("webpage_url") or f"https://www.bilibili.com/video/{video_id}",
            "title": entry.get("title") or "",
            "platform": "bilibili",
        })
    return videos


def normalize_youtube_entries(entries: list[dict]) -> list[dict]:
    videos = []
    seen = set()
    for entry in entries:
        video_id = entry.get("id") or entry.get("url")
        video_url = entry.get("url") or entry.get("webpage_url")
        if not video_id or not video_url or "watch?v=" not in str(video_url) or video_id in seen:
            continue
        seen.add(video_id)
        author_name = (
            entry.get("channel")
            or entry.get("uploader")
            or entry.get("channel_id")
            or entry.get("uploader_id")
            or ""
        )
        videos.append({
            "video_id": str(video_id),
            "video_url": str(video_url),
            "title": entry.get("title") or "",
            "author_name": str(author_name).strip(),
            "view_count": int(entry.get("view_count") or 0),
            "platform": "youtube",
        })
    return sorted(videos, key=lambda item: item.get("view_count") or 0, reverse=True)
