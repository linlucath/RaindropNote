import json
import os
import re
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse

import requests
import yt_dlp
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.routers.note import (
    NOTE_OUTPUT_DIR,
    SUPPORTED_GENERATION_MODE,
    _delete_task_artifacts,
    run_note_task,
)
from app.services.bilibili_uploader_video_service import BilibiliUploaderVideoService
from app.services.note import NoteGenerator
from app.services.cookie_manager import CookieConfigManager
from app.services.progress_state import read_task_status, request_task_cancel, write_task_status
from app.utils.response import ResponseWrapper as R

router = APIRouter()

BATCH_OUTPUT_DIR = Path(NOTE_OUTPUT_DIR) / "batches"
BATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BILIBILI_COOKIES_FILE = os.getenv("BILIBILI_COOKIES_FILE", "cookies.txt")
_batch_lock = Lock()
_batches: dict[str, dict] = {}
_cookie_manager = CookieConfigManager()
_uploader_video_service = BilibiliUploaderVideoService(_cookie_manager.get)


class BatchPreviewRequest(BaseModel):
    space_url: str
    limit: int = Field(default=0, ge=0, le=500)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)


class BatchVideo(BaseModel):
    video_id: str
    video_url: str
    title: str = ""
    platform: Optional[str] = None


class BatchStartRequest(BaseModel):
    videos: list[BatchVideo]
    mode: str = SUPPORTED_GENERATION_MODE
    quality: DownloadQuality = DownloadQuality.fast
    skip_existing: bool = True
    concurrency: int = Field(default=1, ge=1, le=2)
    link: bool = False
    screenshot: bool = False
    model_name: Optional[str] = None
    provider_id: Optional[str] = None
    format: list[str] = Field(default_factory=list)
    style: Optional[str] = None
    extras: Optional[str] = None
    video_understanding: bool = False
    video_interval: int = 0
    grid_size: list[int] = Field(default_factory=list)


class BatchCancelRequest(BaseModel):
    batch_id: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_batch_title(mode: str) -> str:
    return "批量文字稿任务"


def _default_source_label(videos: list[BatchVideo]) -> str:
    if videos:
        platform = videos[0].platform or _infer_platform_from_url(videos[0].video_url)
        if platform == "youtube":
            return "YouTube"
        if platform == "bilibili":
            return "Bilibili"
    return "未知来源"


def create_batch_payload(batch_id: str, request: BatchStartRequest) -> dict:
    now = _now_iso()
    return {
        "batch_id": batch_id,
        "title": _default_batch_title(request.mode),
        "source_label": _default_source_label(request.videos),
        "status": "PENDING",
        "created_at": now,
        "updated_at": now,
        "cancel_requested": False,
        "current_item_title": None,
        "current_item_index": None,
        "total": len(request.videos),
        "completed": 0,
        "items": [
            {
                "video_id": video.video_id,
                "video_url": video.video_url,
                "title": video.title,
                "platform": video.platform or _infer_platform_from_url(video.video_url),
                "status": "PENDING",
                "task_id": None,
                "message": "",
            }
            for video in request.videos
        ],
    }


TERMINAL_BATCH_STATUSES = {"SUCCESS", "FAILED", TaskStatus.CANCELLED.value}
COMPLETED_ITEM_STATUSES = {"SUCCESS", "FAILED", "SKIPPED", TaskStatus.CANCELLED.value}


def _is_batch_terminal(status: Optional[str]) -> bool:
    return status in TERMINAL_BATCH_STATUSES


def _load_batch(batch_id: str) -> Optional[dict]:
    if batch_id in _batches:
        return _batches[batch_id]
    path = BATCH_OUTPUT_DIR / f"{batch_id}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    _batches[batch_id] = payload
    return payload


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


def _infer_platform_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "bilibili.com" in host or "b23.tv" in host:
        return "bilibili"
    return "bilibili"


def _normalize_youtube_channel_url(space_url: str) -> str:
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


def _build_youtube_popular_videos_url(space_url: str) -> str:
    normalized = _normalize_youtube_channel_url(space_url)
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


def _build_youtube_uploads_playlist_url(channel_id: str) -> str | None:
    normalized_channel_id = (channel_id or "").strip()
    if not normalized_channel_id.startswith("UC") or len(normalized_channel_id) <= 2:
        return None
    return f"https://www.youtube.com/playlist?list=UU{normalized_channel_id[2:]}"


def _youtube_request_headers(referer: str) -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": referer,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def _extract_youtube_page_initial_data(page_html: str) -> tuple[dict, dict]:
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


def _parse_youtube_view_count(view_text: str) -> int:
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
    elif re.search(r"\bM\b", normalized, re.IGNORECASE):
        value *= 1000000
    elif re.search(r"\bK\b", normalized, re.IGNORECASE):
        value *= 1000
    return int(value)


def _extract_youtube_lockup_video(lockup: dict) -> dict | None:
    if (lockup or {}).get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
        return None

    video_id = (lockup or {}).get("contentId")
    if not video_id:
        return None

    metadata = (((lockup.get("metadata") or {}).get("lockupMetadataViewModel")) or {})
    title = ((metadata.get("title") or {}).get("content") or "").strip()
    rows = ((((metadata.get("metadata") or {}).get("contentMetadataViewModel")) or {}).get("metadataRows")) or []
    parts = ((rows[0] or {}).get("metadataParts") or []) if rows else []
    view_text = ""
    if parts:
        view_text = ((((parts[0] or {}).get("text")) or {}).get("content") or "").strip()

    return {
        "video_id": str(video_id),
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "title": title,
        "author_name": "",
        "view_count": _parse_youtube_view_count(view_text),
        "platform": "youtube",
    }


def _extract_youtube_videos_from_rich_grid_contents(contents: list[dict]) -> list[dict]:
    videos = []
    seen = set()
    for item in contents:
        lockup = (((item or {}).get("richItemRenderer") or {}).get("content") or {}).get("lockupViewModel")
        if not isinstance(lockup, dict):
            continue
        video = _extract_youtube_lockup_video(lockup)
        if not video or video["video_id"] in seen:
            continue
        seen.add(video["video_id"])
        videos.append(video)
    return videos


def _extract_youtube_rich_grid_continuation_token(contents: list[dict]) -> str | None:
    for item in contents:
        continuation = (((item or {}).get("continuationItemRenderer") or {}).get("continuationEndpoint") or {})
        token = (((continuation.get("continuationCommand") or {}).get("token")) or "").strip()
        if token:
            return token
    return None


def _extract_youtube_page_rich_grid(initial_data: dict) -> tuple[list[dict], str | None]:
    tabs = ((((initial_data.get("contents") or {}).get("twoColumnBrowseResultsRenderer")) or {}).get("tabs")) or []
    for tab in tabs:
        content = (((tab.get("tabRenderer") or {}).get("content")) or {}).get("richGridRenderer")
        if not isinstance(content, dict):
            continue
        contents = content.get("contents") or []
        videos = _extract_youtube_videos_from_rich_grid_contents(contents)
        continuation = _extract_youtube_rich_grid_continuation_token(contents)
        if videos or continuation:
            return videos, continuation
    return [], None


def _extract_youtube_popular_chip_token(initial_data: dict) -> str | None:
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


def _extract_youtube_continuation_rich_grid(payload: dict) -> tuple[list[dict], str | None]:
    actions = payload.get("onResponseReceivedActions") or []
    for action in actions:
        for action_key in ("reloadContinuationItemsCommand", "appendContinuationItemsAction"):
            items = ((((action.get(action_key) or {}).get("continuationItems")))) or []
            videos = _extract_youtube_videos_from_rich_grid_contents(items)
            continuation = _extract_youtube_rich_grid_continuation_token(items)
            if videos or continuation:
                return videos, continuation
    return [], None


def _request_youtube_browse_continuation(
    *,
    api_key: str,
    client_version: str,
    visitor_data: str,
    context: dict,
    continuation: str,
    referer: str,
) -> dict:
    response = requests.post(
        f"https://www.youtube.com/youtubei/v1/browse?prettyPrint=false&key={api_key}",
        headers={
            **_youtube_request_headers(referer),
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


def _preview_youtube_popular_channel_page(
    space_url: str,
    page: int,
    page_size: int,
    limit: int,
) -> dict:
    popular_url = _build_youtube_popular_videos_url(space_url)
    response = requests.get(popular_url, headers=_youtube_request_headers(popular_url), timeout=20)
    response.raise_for_status()

    config, initial_data = _extract_youtube_page_initial_data(response.text)
    initial_videos, initial_continuation = _extract_youtube_page_rich_grid(initial_data)
    popular_chip_token = _extract_youtube_popular_chip_token(initial_data)

    api_key = (config.get("INNERTUBE_API_KEY") or "").strip()
    client_version = (config.get("INNERTUBE_CLIENT_VERSION") or "").strip()
    visitor_data = (config.get("VISITOR_DATA") or "").strip()
    context = dict(config.get("INNERTUBE_CONTEXT") or {})

    if popular_chip_token and api_key and client_version and visitor_data and context:
        payload = _request_youtube_browse_continuation(
            api_key=api_key,
            client_version=client_version,
            visitor_data=visitor_data,
            context=context,
            continuation=popular_chip_token,
            referer=popular_url,
        )
        videos, continuation = _extract_youtube_continuation_rich_grid(payload)
    else:
        videos, continuation = initial_videos, initial_continuation

    if not videos and not continuation:
        raise ValueError("youtube popular page is empty")

    total_needed = page * page_size
    if limit > 0:
        total_needed = min(total_needed, limit)

    seen_video_ids = {video["video_id"] for video in videos}

    while len(videos) < total_needed and continuation and api_key and client_version and visitor_data and context:
        payload = _request_youtube_browse_continuation(
            api_key=api_key,
            client_version=client_version,
            visitor_data=visitor_data,
            context=context,
            continuation=continuation,
            referer=popular_url,
        )
        next_videos, continuation = _extract_youtube_continuation_rich_grid(payload)
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


def _cookie_file_path() -> Path:
    cookies_path = Path(BILIBILI_COOKIES_FILE)
    if cookies_path.is_absolute():
        return cookies_path
    return Path(__file__).parent.parent.parent / BILIBILI_COOKIES_FILE


def _apply_bilibili_cookie(ydl_opts: dict) -> dict:
    cookie = (_cookie_manager.get("bilibili") or "").strip()
    if cookie:
        headers = dict(ydl_opts.get("http_headers") or {})
        headers["Cookie"] = cookie
        ydl_opts["http_headers"] = headers
        return ydl_opts

    cookies_path = _cookie_file_path()
    if cookies_path.exists():
        ydl_opts["cookiefile"] = str(cookies_path)
        return ydl_opts

    return ydl_opts


def _extract_flat_playlist(space_url: str, limit: int = 0, start: Optional[int] = None, end: Optional[int] = None) -> dict:
    platform = _infer_platform_from_url(space_url)
    ydl_opts = {
        "extract_flat": True,
        "skip_download": True,
        "quiet": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    }
    if platform == "youtube":
        ydl_opts["http_headers"] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.youtube.com/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    if start is not None:
        ydl_opts["playliststart"] = start
    if end is not None:
        ydl_opts["playlistend"] = end
    elif limit > 0:
        ydl_opts["playlistend"] = limit
    if platform == "bilibili":
        ydl_opts = _apply_bilibili_cookie(ydl_opts)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(space_url, download=False)


def _apply_default_bilibili_space_order(space_url: str) -> str:
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


def _parse_bilibili_space_video_request(space_url: str) -> tuple[str | None, str]:
    parsed = urlparse(space_url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "space.bilibili.com":
        return None, "click"

    path_parts = [segment for segment in parsed.path.rstrip("/").split("/") if segment]
    if len(path_parts) == 2 and path_parts[0].isdigit() and path_parts[1] == "video":
        pass
    elif len(path_parts) == 3 and path_parts[0].isdigit() and path_parts[1] == "upload" and path_parts[2] == "video":
        pass
    else:
        return None, "click"

    query = parse_qs(parsed.query)
    order = (query.get("order") or ["click"])[0] or "click"
    return path_parts[0], order


def _extract_video_metadata(video_url: str) -> dict:
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "socket_timeout": 10,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    }
    ydl_opts = _apply_bilibili_cookie(ydl_opts)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(video_url, download=False)


def _enrich_missing_titles(videos: list[dict]) -> list[dict]:
    missing_title_indexes = [index for index, video in enumerate(videos) if not video.get("title")]
    if not missing_title_indexes:
        return videos

    enriched = [dict(video) for video in videos]
    max_workers = min(8, len(missing_title_indexes))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_extract_video_metadata, enriched[index]["video_url"]): index
            for index in missing_title_indexes
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                metadata = future.result()
            except Exception:
                continue
            title = (metadata.get("title") or "").strip()
            if title:
                enriched[index]["title"] = title

    retry_indexes = [index for index in missing_title_indexes if not enriched[index].get("title")]
    for index in retry_indexes:
        try:
            metadata = _extract_video_metadata(enriched[index]["video_url"])
        except Exception:
            continue
        title = (metadata.get("title") or "").strip()
        if title:
            enriched[index]["title"] = title
    return enriched


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


def mark_processed_videos(videos: list[dict], mode: Optional[str] = None) -> list[dict]:
    marked_videos = []
    for video in videos:
        marked_video = dict(video)
        existing_task_id = find_existing_task_id(str(video.get("video_id") or ""), mode)
        if existing_task_id:
            marked_video["processed_task_id"] = existing_task_id
        marked_videos.append(marked_video)
    return marked_videos


def mark_processed_page_items(payload: dict, mode: Optional[str] = None) -> dict:
    return {
        **payload,
        "items": mark_processed_videos(payload.get("items") or [], mode),
    }


def preview_bilibili_space_page(
    space_url: str,
    page: int = 1,
    page_size: int = 20,
    limit: int = 0,
) -> dict:
    if _infer_platform_from_url(space_url) == "youtube":
        try:
            return mark_processed_page_items(
                _preview_youtube_popular_channel_page(
                    space_url=space_url,
                    page=page,
                    page_size=page_size,
                    limit=limit,
                )
            )
        except Exception:
            pass

        normalized_channel_url = _normalize_youtube_channel_url(space_url)
        start = (page - 1) * page_size + 1
        if limit > 0 and start > limit:
            return {
                "items": [],
                "page": page,
                "page_size": page_size,
                "has_more": False,
                "total": limit,
            }

        extra_probe = 1
        if limit > 0:
            remaining = limit - start + 1
            fetch_size = max(min(page_size + extra_probe, remaining), 0)
        else:
            fetch_size = page_size + extra_probe

        if fetch_size <= 0:
            return {
                "items": [],
                "page": page,
                "page_size": page_size,
                "has_more": False,
                "total": limit if limit > 0 else None,
            }

        end = start + fetch_size - 1
        data = _extract_flat_playlist(normalized_channel_url, start=start, end=end)
        videos = normalize_youtube_entries(data.get("entries") or [])[:fetch_size]
        if not videos:
            uploads_playlist_url = _build_youtube_uploads_playlist_url(data.get("channel_id") or "")
            if uploads_playlist_url:
                uploads_data = _extract_flat_playlist(uploads_playlist_url, start=start, end=end)
                videos = normalize_youtube_entries(uploads_data.get("entries") or [])[:fetch_size]
        return mark_processed_page_items({
            "items": videos[:page_size],
            "page": page,
            "page_size": page_size,
            "has_more": len(videos) > page_size,
            "total": limit if limit > 0 else None,
        })

    mid, order = _parse_bilibili_space_video_request(space_url)
    if mid:
        return mark_processed_page_items(
            _uploader_video_service.get_uploader_videos_page(
                mid=mid,
                page=page,
                page_size=page_size,
                limit=limit,
                order=order,
            )
        )

    space_url = _apply_default_bilibili_space_order(space_url)
    start = (page - 1) * page_size + 1
    if limit > 0 and start > limit:
        return {
            "items": [],
            "page": page,
            "page_size": page_size,
            "has_more": False,
            "total": limit,
        }

    extra_probe = 1
    if limit > 0:
        remaining = limit - start + 1
        fetch_size = max(min(page_size + extra_probe, remaining), 0)
    else:
        fetch_size = page_size + extra_probe

    if fetch_size <= 0:
        return {
            "items": [],
            "page": page,
            "page_size": page_size,
            "has_more": False,
            "total": limit if limit > 0 else None,
        }

    end = start + fetch_size - 1
    data = _extract_flat_playlist(space_url, start=start, end=end)
    videos = normalize_bilibili_entries(data.get("entries") or [])[:fetch_size]
    has_more = len(videos) > page_size
    visible_videos = _enrich_missing_titles(videos[:page_size])
    total = limit if limit > 0 else None
    return mark_processed_page_items({
        "items": visible_videos,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
        "total": total,
    })



def _infer_result_mode(result_content: dict | str) -> str:
    if isinstance(result_content, dict):
        mode = result_content.get("mode")
        if mode in {SUPPORTED_GENERATION_MODE, "transcript", "note"}:
            return mode
        markdown = result_content.get("markdown") or ""
    else:
        markdown = result_content

    if "## 校对文字稿" in markdown:
        return "polished_transcript"
    if "## 简体中文文字稿" in markdown:
        return "transcript"
    return "note"


def find_existing_task_id(video_id: str, mode: Optional[str] = None) -> Optional[str]:
    output_dir = Path(NOTE_OUTPUT_DIR)
    requested_mode = mode or SUPPORTED_GENERATION_MODE
    matched_task_id = None
    for path in output_dir.glob("*.json"):
        name = path.name
        if name.endswith(".status.json") or path.stem.endswith("_audio") or path.stem.endswith("_transcript"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (data.get("audio_meta") or {}).get("video_id") != video_id:
            continue
        result_mode = _infer_result_mode(data)
        if result_mode != SUPPORTED_GENERATION_MODE:
            _delete_task_artifacts(path.stem, output_dir)
            NoteGenerator.delete_note(task_id=path.stem)
            continue
        if requested_mode != SUPPORTED_GENERATION_MODE:
            continue
        if result_mode != requested_mode:
            continue
        if matched_task_id is None:
            matched_task_id = path.stem
    return matched_task_id


def _save_batch(batch: dict) -> None:
    BATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = BATCH_OUTPUT_DIR / f"{batch['batch_id']}.json"
    path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")


def _update_batch(batch_id: str, **updates) -> dict:
    with _batch_lock:
        batch = _batches[batch_id]
        batch.update(updates)
        batch["updated_at"] = _now_iso()
        completed = sum(1 for item in batch["items"] if item["status"] in COMPLETED_ITEM_STATUSES)
        batch["completed"] = completed
        batch["total"] = len(batch["items"])
        if batch.get("cancel_requested") and completed == batch["total"]:
            batch["status"] = TaskStatus.CANCELLED.value
        elif completed == batch["total"] and not _is_batch_terminal(batch.get("status")):
            batch["status"] = "SUCCESS" if all(item["status"] in {"SUCCESS", "SKIPPED"} for item in batch["items"]) else "FAILED"
        _save_batch(batch)
        return batch


def _set_item(batch_id: str, index: int, **updates) -> None:
    with _batch_lock:
        batch = _batches[batch_id]
        batch["items"][index].update(updates)
        batch["updated_at"] = _now_iso()
        completed = sum(1 for item in batch["items"] if item["status"] in COMPLETED_ITEM_STATUSES)
        batch["completed"] = completed
        batch["total"] = len(batch["items"])
        if batch.get("cancel_requested") and completed == batch["total"]:
            batch["status"] = TaskStatus.CANCELLED.value
        _save_batch(batch)


def _is_cancel_requested(batch_id: str) -> bool:
    return bool(_batches[batch_id].get("cancel_requested"))


def _finalize_batch_cancel(batch_id: str, message: str = "批量任务已取消") -> dict:
    with _batch_lock:
        batch = _batches[batch_id]
        for item in batch["items"]:
            if item["status"] == "PENDING":
                item["status"] = TaskStatus.CANCELLED.value
                item["message"] = message
        batch["status"] = TaskStatus.CANCELLED.value
        batch["cancel_requested"] = True
        batch["current_item_title"] = None
        batch["current_item_index"] = None
        batch["updated_at"] = _now_iso()
        batch["completed"] = sum(1 for item in batch["items"] if item["status"] in COMPLETED_ITEM_STATUSES)
        batch["total"] = len(batch["items"])
        _save_batch(batch)
        return batch


def _request_current_child_cancel(batch: dict) -> None:
    for item in batch.get("items") or []:
        if item.get("status") != "RUNNING":
            continue
        task_id = item.get("task_id")
        if task_id:
            request_task_cancel(task_id=task_id, output_dir=Path(NOTE_OUTPUT_DIR))


def _sync_child_cancel_status(batch_id: str, index: int) -> bool:
    item = _batches[batch_id]["items"][index]
    task_id = item.get("task_id")
    if not task_id:
        return False
    task_status = read_task_status(task_id=task_id, output_dir=Path(NOTE_OUTPUT_DIR))
    if task_status.get("status") != TaskStatus.CANCELLED.value:
        return False
    _set_item(
        batch_id,
        index,
        status=TaskStatus.CANCELLED.value,
        message=task_status.get("message", "任务已取消"),
    )
    return True


def _run_batch_item(batch_id: str, request: BatchStartRequest, index: int, video: BatchVideo) -> None:
    if _is_cancel_requested(batch_id):
        return

    _update_batch(batch_id, current_item_title=video.title or None, current_item_index=index)
    existing_task_id = find_existing_task_id(video.video_id, request.mode) if request.skip_existing else None
    if existing_task_id:
        _set_item(batch_id, index, status="SKIPPED", task_id=existing_task_id, message="已存在，已跳过")
        return

    task_id = str(uuid.uuid4())
    _set_item(batch_id, index, status="RUNNING", task_id=task_id, message="")
    write_task_status(
        task_id=task_id,
        output_dir=Path(NOTE_OUTPUT_DIR),
        status=TaskStatus.PENDING,
        title=video.title,
        platform=video.platform or _infer_platform_from_url(video.video_url),
    )
    try:
        platform = video.platform or _infer_platform_from_url(video.video_url)
        run_note_task(
            task_id=task_id,
            video_url=video.video_url,
            platform=platform,
            quality=request.quality,
            link=request.link,
            screenshot=request.screenshot,
            model_name=request.model_name,
            provider_id=request.provider_id,
            _format=request.format,
            style=request.style,
            extras=request.extras,
            video_understanding=request.video_understanding,
            video_interval=request.video_interval,
            grid_size=request.grid_size,
            mode=request.mode,
        )
        result_path = Path(NOTE_OUTPUT_DIR) / f"{task_id}.json"
        if result_path.exists():
            _set_item(batch_id, index, status="SUCCESS", message="")
        elif _sync_child_cancel_status(batch_id, index):
            pass
        else:
            _set_item(batch_id, index, status="FAILED", message="任务未生成结果文件")
    except Exception as exc:
        _set_item(batch_id, index, status="FAILED", message=str(exc))


def run_batch(batch_id: str, request: BatchStartRequest) -> None:
    if _is_cancel_requested(batch_id):
        _finalize_batch_cancel(batch_id)
        return

    _update_batch(batch_id, status="RUNNING")
    max_workers = max(1, min(request.concurrency, len(request.videos)))

    if max_workers == 1:
        for index, video in enumerate(request.videos):
            if _is_cancel_requested(batch_id):
                _finalize_batch_cancel(batch_id)
                return
            _run_batch_item(batch_id, request, index, video)
    else:
        next_index = 0
        in_flight: dict = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while next_index < len(request.videos) and len(in_flight) < max_workers:
                if _is_cancel_requested(batch_id):
                    break
                future = executor.submit(
                    _run_batch_item,
                    batch_id,
                    request,
                    next_index,
                    request.videos[next_index],
                )
                in_flight[future] = next_index
                next_index += 1

            while in_flight:
                done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
                for future in done:
                    in_flight.pop(future, None)
                    future.result()

                while next_index < len(request.videos) and len(in_flight) < max_workers:
                    if _is_cancel_requested(batch_id):
                        break
                    future = executor.submit(
                        _run_batch_item,
                        batch_id,
                        request,
                        next_index,
                        request.videos[next_index],
                    )
                    in_flight[future] = next_index
                    next_index += 1

                if _is_cancel_requested(batch_id) and not in_flight:
                    break

    if _is_cancel_requested(batch_id):
        _finalize_batch_cancel(batch_id)
        return

    _update_batch(batch_id, current_item_title=None, current_item_index=None)


@router.post("/batch/preview")
def batch_preview(data: BatchPreviewRequest):
    return R.success(preview_bilibili_space_page(
        data.space_url,
        page=data.page,
        page_size=data.page_size,
        limit=data.limit,
    ))


@router.post("/batch/start")
def batch_start(data: BatchStartRequest, background_tasks: BackgroundTasks):
    if data.mode != SUPPORTED_GENERATION_MODE:
        return R.error(msg="当前仅支持校对文字稿模式", code=400)
    batch_id = str(uuid.uuid4())
    batch = create_batch_payload(batch_id=batch_id, request=data)
    with _batch_lock:
        _batches[batch_id] = batch
        _save_batch(batch)
    background_tasks.add_task(run_batch, batch_id, data)
    return R.success({"batch_id": batch_id})


@router.post("/batch/cancel")
def batch_cancel(data: BatchCancelRequest):
    batch = _load_batch(data.batch_id)
    if not batch:
        return R.error(msg="批量任务不存在", code=404)

    if _is_batch_terminal(batch.get("status")) or batch.get("cancel_requested"):
        return R.success(batch)

    updated_batch = _update_batch(
        data.batch_id,
        status=TaskStatus.CANCELLING.value,
        cancel_requested=True,
    )
    _request_current_child_cancel(updated_batch)
    return R.success(updated_batch)


@router.get("/batch/status/{batch_id}")
def batch_status(batch_id: str):
    batch = _load_batch(batch_id)
    if batch:
        return R.success(batch)
    return R.error(msg="批量任务不存在", code=404)
