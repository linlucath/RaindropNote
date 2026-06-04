import os
from pathlib import Path
from typing import Optional

import requests
import yt_dlp

from app.services.bilibili_uploader_video_service import BilibiliUploaderVideoService
from app.services.cookie_manager import CookieConfigManager
from app.services.batch_preview_normalizers import (
    normalize_bilibili_entries,
    normalize_youtube_entries,
)
from app.services.batch_preview_url_rules import (
    apply_default_bilibili_space_order,
    build_youtube_popular_videos_url,
    build_youtube_uploads_playlist_url,
    infer_platform_from_url,
    normalize_youtube_channel_url,
    parse_bilibili_space_video_request,
)
from app.services import batch_preview_youtube
from app.services import batch_preview_dispatch
from app.services import batch_preview_ytdlp

BILIBILI_COOKIES_FILE = os.getenv("BILIBILI_COOKIES_FILE", "cookies.txt")

_cookie_manager = CookieConfigManager()
_uploader_video_service = BilibiliUploaderVideoService(_cookie_manager.get)

# Compatibility aliases for old private helpers. app.routers.batch still exposes
# these names for existing tests and sibling routers while the implementation is
# split across focused modules.
_normalize_youtube_channel_url = normalize_youtube_channel_url
_build_youtube_popular_videos_url = build_youtube_popular_videos_url
_build_youtube_uploads_playlist_url = build_youtube_uploads_playlist_url
_apply_default_bilibili_space_order = apply_default_bilibili_space_order
_parse_bilibili_space_video_request = parse_bilibili_space_video_request
_youtube_request_headers = batch_preview_youtube.youtube_request_headers
_extract_youtube_page_initial_data = batch_preview_youtube.extract_youtube_page_initial_data
_parse_youtube_view_count = batch_preview_youtube.parse_youtube_view_count
_extract_youtube_lockup_video = batch_preview_youtube.extract_youtube_lockup_video
_extract_youtube_videos_from_rich_grid_contents = batch_preview_youtube.extract_youtube_videos_from_rich_grid_contents
_extract_youtube_rich_grid_continuation_token = batch_preview_youtube.extract_youtube_rich_grid_continuation_token
_extract_youtube_page_rich_grid = batch_preview_youtube.extract_youtube_page_rich_grid
_extract_youtube_popular_chip_token = batch_preview_youtube.extract_youtube_popular_chip_token
_extract_youtube_continuation_rich_grid = batch_preview_youtube.extract_youtube_continuation_rich_grid


def _request_youtube_browse_continuation(
    *,
    api_key: str,
    client_version: str,
    visitor_data: str,
    context: dict,
    continuation: str,
    referer: str,
) -> dict:
    return batch_preview_youtube.request_youtube_browse_continuation(
        api_key=api_key,
        client_version=client_version,
        visitor_data=visitor_data,
        context=context,
        continuation=continuation,
        referer=referer,
        requests_module=requests,
    )


def _preview_youtube_popular_channel_page(
    space_url: str,
    page: int,
    page_size: int,
    limit: int,
) -> dict:
    return batch_preview_youtube.preview_youtube_popular_channel_page(
        space_url=space_url,
        page=page,
        page_size=page_size,
        limit=limit,
        requests_module=requests,
        build_popular_url=_build_youtube_popular_videos_url,
        request_headers=_youtube_request_headers,
        extract_initial_data=_extract_youtube_page_initial_data,
        extract_page_rich_grid=_extract_youtube_page_rich_grid,
        extract_popular_chip_token=_extract_youtube_popular_chip_token,
        request_continuation=_request_youtube_browse_continuation,
        extract_continuation_rich_grid=_extract_youtube_continuation_rich_grid,
    )


def _cookie_file_path() -> Path:
    return batch_preview_ytdlp.cookie_file_path(BILIBILI_COOKIES_FILE)


def _apply_bilibili_cookie(ydl_opts: dict) -> dict:
    return batch_preview_ytdlp.apply_bilibili_cookie_with_path(
        ydl_opts,
        cookie_manager=_cookie_manager,
        cookies_file=BILIBILI_COOKIES_FILE,
        cookie_path=_cookie_file_path,
    )


def _extract_flat_playlist(
    space_url: str,
    limit: int = 0,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> dict:
    return batch_preview_ytdlp.extract_flat_playlist(
        space_url,
        limit=limit,
        start=start,
        end=end,
        infer_platform=infer_platform_from_url,
        apply_cookie=_apply_bilibili_cookie,
        yt_dlp_module=yt_dlp,
    )


def _extract_video_metadata(video_url: str) -> dict:
    return batch_preview_ytdlp.extract_video_metadata(
        video_url,
        apply_cookie=_apply_bilibili_cookie,
        yt_dlp_module=yt_dlp,
    )


def _enrich_missing_titles(videos: list[dict]) -> list[dict]:
    return batch_preview_ytdlp.enrich_missing_titles(
        videos,
        extract_metadata=_extract_video_metadata,
    )


def preview_bilibili_space(space_url: str, limit: int = 10) -> list[dict]:
    mid, order = _parse_bilibili_space_video_request(space_url)
    if mid:
        page = _uploader_video_service.get_uploader_videos_page(
            mid=mid,
            page=1,
            page_size=limit if limit > 0 else 10,
            limit=limit,
            order=order,
        )
        return page["items"]

    data = _extract_flat_playlist(_apply_default_bilibili_space_order(space_url), limit)
    videos = normalize_bilibili_entries(data.get("entries") or [])
    limited_videos = videos[:limit] if limit > 0 else videos
    return _enrich_missing_titles(limited_videos)


def _empty_page(page: int, page_size: int, total: int | None) -> dict:
    return {
        "items": [],
        "page": page,
        "page_size": page_size,
        "has_more": False,
        "total": total,
    }


def _page_fetch_window(page: int, page_size: int, limit: int) -> tuple[int, int] | None:
    start = (page - 1) * page_size + 1
    if limit > 0 and start > limit:
        return None

    extra_probe = 1
    if limit > 0:
        remaining = limit - start + 1
        fetch_size = max(min(page_size + extra_probe, remaining), 0)
    else:
        fetch_size = page_size + extra_probe

    if fetch_size <= 0:
        return None
    return start, start + fetch_size - 1


def _preview_youtube_fallback_page(space_url: str, page: int, page_size: int, limit: int) -> dict:
    normalized_channel_url = _normalize_youtube_channel_url(space_url)
    fetch_window = _page_fetch_window(page, page_size, limit)
    if fetch_window is None:
        return _empty_page(page, page_size, limit if limit > 0 else None)

    start, end = fetch_window
    fetch_size = end - start + 1
    data = _extract_flat_playlist(normalized_channel_url, start=start, end=end)
    videos = normalize_youtube_entries(data.get("entries") or [])[:fetch_size]
    if not videos:
        uploads_playlist_url = _build_youtube_uploads_playlist_url(data.get("channel_id") or "")
        if uploads_playlist_url:
            uploads_data = _extract_flat_playlist(uploads_playlist_url, start=start, end=end)
            videos = normalize_youtube_entries(uploads_data.get("entries") or [])[:fetch_size]
    return {
        "items": videos[:page_size],
        "page": page,
        "page_size": page_size,
        "has_more": len(videos) > page_size,
        "total": limit if limit > 0 else None,
    }


def _preview_bilibili_flat_page(space_url: str, page: int, page_size: int, limit: int) -> dict:
    space_url = _apply_default_bilibili_space_order(space_url)
    fetch_window = _page_fetch_window(page, page_size, limit)
    if fetch_window is None:
        return _empty_page(page, page_size, limit if limit > 0 else None)

    start, end = fetch_window
    fetch_size = end - start + 1
    data = _extract_flat_playlist(space_url, start=start, end=end)
    videos = normalize_bilibili_entries(data.get("entries") or [])[:fetch_size]
    has_more = len(videos) > page_size
    visible_videos = _enrich_missing_titles(videos[:page_size])
    total = limit if limit > 0 else None
    return {
        "items": visible_videos,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
        "total": total,
    }


def preview_bilibili_space_page(
    space_url: str,
    page: int = 1,
    page_size: int = 20,
    limit: int = 0,
) -> dict:
    return batch_preview_dispatch.preview_space_page(
        space_url,
        page=page,
        page_size=page_size,
        limit=limit,
        infer_platform=infer_platform_from_url,
        preview_youtube_popular=_preview_youtube_popular_channel_page,
        preview_youtube_fallback=_preview_youtube_fallback_page,
        parse_bilibili_space_request=_parse_bilibili_space_video_request,
        uploader_video_service=_uploader_video_service,
        preview_bilibili_flat=_preview_bilibili_flat_page,
    )
