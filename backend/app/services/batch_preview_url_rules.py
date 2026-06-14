from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse


def infer_platform_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "bilibili.com" in host or "b23.tv" in host:
        return "bilibili"
    return "bilibili"


def normalize_youtube_channel_url(space_url: str) -> str:
    parsed = urlparse(space_url)
    if parsed.scheme not in {"http", "https"}:
        return space_url
    host = parsed.netloc.lower()
    if host not in {"www.youtube.com", "youtube.com", "m.youtube.com"}:
        return space_url

    path = parsed.path.rstrip("/")
    if not path.startswith("/@"):
        return space_url
    if path.endswith("/videos"):
        return space_url

    return urlunparse(parsed._replace(path=f"{path}/videos", query=""))


def build_youtube_popular_videos_url(space_url: str) -> str:
    normalized = normalize_youtube_channel_url(space_url)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        return normalized

    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    filtered_items = [(key, value) for key, value in query_items if key not in {"view", "sort", "flow"}]
    filtered_items.extend([
        ("view", "0"),
        ("sort", "p"),
        ("flow", "grid"),
    ])
    return urlunparse(parsed._replace(query=urlencode(filtered_items)))


def build_youtube_uploads_playlist_url(channel_id: str) -> str | None:
    normalized_channel_id = (channel_id or "").strip()
    if not normalized_channel_id.startswith("UC") or len(normalized_channel_id) <= 2:
        return None
    return f"https://www.youtube.com/playlist?list=UU{normalized_channel_id[2:]}"


def apply_default_bilibili_space_order(space_url: str) -> str:
    parsed = urlparse(space_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "space.bilibili.com":
        return space_url
    path = parsed.path.rstrip("/")
    path_parts = [segment for segment in path.split("/") if segment]
    if len(path_parts) != 3 or not path_parts[0].isdigit() or path_parts[-1] != "video":
        return space_url

    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    if any(key == "order" and value for key, value in query_items):
        return space_url

    query_items.append(("order", "click"))
    return urlunparse(parsed._replace(query=urlencode(query_items)))


def parse_bilibili_space_video_request(space_url: str) -> tuple[str | None, str]:
    parsed = urlparse(space_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "space.bilibili.com":
        return None, "click"

    path_parts = [segment for segment in parsed.path.rstrip("/").split("/") if segment]
    if len(path_parts) == 1 and path_parts[0].isdigit():
        pass
    elif len(path_parts) == 2 and path_parts[0].isdigit() and path_parts[1] == "video":
        pass
    elif len(path_parts) == 3 and path_parts[0].isdigit() and path_parts[1] == "upload" and path_parts[2] == "video":
        pass
    else:
        return None, "click"

    query = parse_qs(parsed.query)
    order = (query.get("order") or ["click"])[0] or "click"
    return path_parts[0], order
