import json
import re


def extract_youtube_page_initial_data(page_html: str) -> tuple[dict, dict]:
    config = {}
    for match in re.finditer(r"ytcfg\.set\((\{.*?\})\);", page_html):
        try:
            config.update(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue

    initial_match = re.search(r"var ytInitialData = (\{.*?\});</script>", page_html)
    if not initial_match:
        raise ValueError("ytInitialData not found")

    initial_data = json.loads(initial_match.group(1))
    return config, initial_data


def parse_youtube_view_count(view_text: str | None) -> int:
    normalized = (view_text or "").strip().replace(",", "")
    if not normalized:
        return 0

    match = re.search(r"(\d+(?:\.\d+)?)", normalized)
    if not match:
        return 0

    value = float(match.group(1))
    if "亿" in normalized:
        value *= 100000000
    elif "万" in normalized:
        value *= 10000
    elif re.search(r"\d(?:\.\d+)?\s*M", normalized, re.IGNORECASE):
        value *= 1000000
    elif re.search(r"\d(?:\.\d+)?\s*K", normalized, re.IGNORECASE):
        value *= 1000
    return int(value)


def _text_content(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    content = value.get("content")
    if isinstance(content, str):
        return content.strip()
    runs = value.get("runs")
    if isinstance(runs, list):
        return "".join(str(run.get("text") or "") for run in runs if isinstance(run, dict)).strip()
    return ""


def _metadata_part_text(part: object) -> str:
    if not isinstance(part, dict):
        return ""
    return _text_content(part.get("text"))


def _extract_youtube_author(metadata: dict, lockup: dict) -> str:
    candidates = [
        metadata.get("ownerText"),
        metadata.get("shortBylineText"),
        metadata.get("longBylineText"),
        metadata.get("subtitle"),
        lockup.get("ownerText"),
        lockup.get("shortBylineText"),
        lockup.get("longBylineText"),
    ]
    for candidate in candidates:
        text = _text_content(candidate)
        if text:
            return text

    rows = ((((metadata.get("metadata") or {}).get("contentMetadataViewModel")) or {}).get("metadataRows")) or []
    if len(rows) < 2:
        return ""
    parts = (rows[1] or {}).get("metadataParts") or []
    for part in parts:
        text = _metadata_part_text(part)
        if text:
            return text
    return ""


def extract_youtube_lockup_video(lockup: dict) -> dict | None:
    if (lockup or {}).get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
        return None

    video_id = (lockup or {}).get("contentId")
    if not video_id:
        return None

    metadata = (((lockup.get("metadata") or {}).get("lockupMetadataViewModel")) or {})
    title = _text_content(metadata.get("title"))
    rows = ((((metadata.get("metadata") or {}).get("contentMetadataViewModel")) or {}).get("metadataRows")) or []
    parts = ((rows[0] or {}).get("metadataParts") or []) if rows else []
    view_text = ""
    if parts:
        view_text = _metadata_part_text(parts[0])

    return {
        "video_id": str(video_id),
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "title": title,
        "author_name": _extract_youtube_author(metadata, lockup),
        "view_count": parse_youtube_view_count(view_text),
        "platform": "youtube",
    }


def extract_youtube_videos_from_rich_grid_contents(contents: list[dict]) -> list[dict]:
    videos = []
    seen = set()
    for item in contents:
        lockup = (((item or {}).get("richItemRenderer") or {}).get("content") or {}).get("lockupViewModel")
        if not isinstance(lockup, dict):
            continue
        video = extract_youtube_lockup_video(lockup)
        if not video or video["video_id"] in seen:
            continue
        seen.add(video["video_id"])
        videos.append(video)
    return videos


def extract_youtube_rich_grid_continuation_token(contents: list[dict]) -> str | None:
    for item in contents:
        continuation = (((item or {}).get("continuationItemRenderer") or {}).get("continuationEndpoint") or {})
        token = (((continuation.get("continuationCommand") or {}).get("token")) or "").strip()
        if token:
            return token
    return None


def extract_youtube_page_rich_grid(initial_data: dict) -> tuple[list[dict], str | None]:
    tabs = ((((initial_data.get("contents") or {}).get("twoColumnBrowseResultsRenderer")) or {}).get("tabs")) or []
    for tab in tabs:
        content = (((tab.get("tabRenderer") or {}).get("content")) or {}).get("richGridRenderer")
        if not isinstance(content, dict):
            continue
        contents = content.get("contents") or []
        videos = extract_youtube_videos_from_rich_grid_contents(contents)
        continuation = extract_youtube_rich_grid_continuation_token(contents)
        if videos or continuation:
            return videos, continuation
    return [], None


def extract_youtube_popular_chip_token(initial_data: dict) -> str | None:
    tabs = ((((initial_data.get("contents") or {}).get("twoColumnBrowseResultsRenderer")) or {}).get("tabs")) or []
    for tab in tabs:
        content = (((tab.get("tabRenderer") or {}).get("content")) or {}).get("richGridRenderer")
        if not isinstance(content, dict):
            continue
        chips = ((((content.get("header") or {}).get("chipBarViewModel")) or {}).get("chips")) or []
        for chip in chips:
            chip_view = chip.get("chipViewModel") or {}
            label = ((chip_view.get("text") or "") or chip_view.get("accessibilityLabel") or "").strip().lower()
            if label not in {"最热门", "popular", "most popular"}:
                continue
            innertube_command = (((chip_view.get("tapCommand") or {}).get("innertubeCommand")) or {})
            token = (((innertube_command.get("continuationCommand") or {}).get("token")) or "").strip()
            if token:
                return token
    return None


def extract_youtube_continuation_rich_grid(payload: dict) -> tuple[list[dict], str | None]:
    actions = payload.get("onResponseReceivedActions") or []
    for action in actions:
        for action_key in ("reloadContinuationItemsCommand", "appendContinuationItemsAction"):
            items = ((((action.get(action_key) or {}).get("continuationItems")))) or []
            videos = extract_youtube_videos_from_rich_grid_contents(items)
            continuation = extract_youtube_rich_grid_continuation_token(items)
            if videos or continuation:
                return videos, continuation
    return [], None
