import requests

from app.services import batch_preview_youtube_extractors as extractors
from app.services.batch_preview_url_rules import build_youtube_popular_videos_url


def youtube_request_headers(referer: str) -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": referer,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def extract_youtube_page_initial_data(page_html: str) -> tuple[dict, dict]:
    return extractors.extract_youtube_page_initial_data(page_html)


def parse_youtube_view_count(view_text: str | None) -> int:
    return extractors.parse_youtube_view_count(view_text)


def extract_youtube_lockup_video(lockup: dict) -> dict | None:
    return extractors.extract_youtube_lockup_video(lockup)


def extract_youtube_videos_from_rich_grid_contents(contents: list[dict]) -> list[dict]:
    return extractors.extract_youtube_videos_from_rich_grid_contents(contents)


def extract_youtube_rich_grid_continuation_token(contents: list[dict]) -> str | None:
    return extractors.extract_youtube_rich_grid_continuation_token(contents)


def extract_youtube_page_rich_grid(initial_data: dict) -> tuple[list[dict], str | None]:
    return extractors.extract_youtube_page_rich_grid(initial_data)


def extract_youtube_popular_chip_token(initial_data: dict) -> str | None:
    return extractors.extract_youtube_popular_chip_token(initial_data)


def extract_youtube_continuation_rich_grid(payload: dict) -> tuple[list[dict], str | None]:
    return extractors.extract_youtube_continuation_rich_grid(payload)


def request_youtube_browse_continuation(
    *,
    api_key: str,
    client_version: str,
    visitor_data: str,
    context: dict,
    continuation: str,
    referer: str,
    requests_module=requests,
) -> dict:
    response = requests_module.post(
        f"https://www.youtube.com/youtubei/v1/browse?prettyPrint=false&key={api_key}",
        headers={
            **youtube_request_headers(referer),
            "Content-Type": "application/json",
            "Origin": "https://www.youtube.com",
            "X-Goog-Visitor-Id": visitor_data,
            "X-YouTube-Client-Name": "1",
            "X-YouTube-Client-Version": client_version,
        },
        json={
            "context": context,
            "continuation": continuation,
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def preview_youtube_popular_channel_page(
    space_url: str,
    page: int,
    page_size: int,
    limit: int,
    *,
    requests_module=requests,
    build_popular_url=build_youtube_popular_videos_url,
    request_headers=youtube_request_headers,
    extract_initial_data=extract_youtube_page_initial_data,
    extract_page_rich_grid=extract_youtube_page_rich_grid,
    extract_popular_chip_token=extract_youtube_popular_chip_token,
    request_continuation=request_youtube_browse_continuation,
    extract_continuation_rich_grid=extract_youtube_continuation_rich_grid,
) -> dict:
    popular_url = build_popular_url(space_url)
    response = requests_module.get(popular_url, headers=request_headers(popular_url), timeout=20)
    response.raise_for_status()

    config, initial_data = extract_initial_data(response.text)
    initial_videos, initial_continuation = extract_page_rich_grid(initial_data)
    popular_chip_token = extract_popular_chip_token(initial_data)

    api_key = (config.get("INNERTUBE_API_KEY") or "").strip()
    client_version = (config.get("INNERTUBE_CLIENT_VERSION") or "").strip()
    visitor_data = (config.get("VISITOR_DATA") or "").strip()
    context = dict(config.get("INNERTUBE_CONTEXT") or {})

    if popular_chip_token and api_key and client_version and visitor_data and context:
        payload = request_continuation(
            api_key=api_key,
            client_version=client_version,
            visitor_data=visitor_data,
            context=context,
            continuation=popular_chip_token,
            referer=popular_url,
        )
        videos, continuation = extract_continuation_rich_grid(payload)
    else:
        videos, continuation = initial_videos, initial_continuation

    if not videos and not continuation:
        raise ValueError("youtube popular page is empty")

    total_needed = page * page_size
    if limit > 0:
        total_needed = min(total_needed, limit)

    seen_video_ids = {video["video_id"] for video in videos}

    while len(videos) < total_needed and continuation and api_key and client_version and visitor_data and context:
        payload = request_continuation(
            api_key=api_key,
            client_version=client_version,
            visitor_data=visitor_data,
            context=context,
            continuation=continuation,
            referer=popular_url,
        )
        next_videos, continuation = extract_continuation_rich_grid(payload)
        if not next_videos:
            break
        for video in next_videos:
            if video["video_id"] in seen_video_ids:
                continue
            seen_video_ids.add(video["video_id"])
            videos.append(video)

    if limit > 0:
        videos = videos[:limit]

    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    items = videos[start_index:end_index]
    has_more = end_index < len(videos) or (limit <= 0 and continuation is not None)
    total = limit if limit > 0 else None
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
        "total": total,
    }
