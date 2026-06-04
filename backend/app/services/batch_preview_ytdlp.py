from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

import yt_dlp


def cookie_file_path(cookies_file: str) -> Path:
    cookies_path = Path(cookies_file)
    if cookies_path.is_absolute():
        return cookies_path
    return Path(__file__).parent.parent.parent / cookies_file


def apply_bilibili_cookie(ydl_opts: dict, *, cookie_manager, cookies_file: str) -> dict:
    cookie = (cookie_manager.get("bilibili") or "").strip()
    if cookie:
        headers = dict(ydl_opts.get("http_headers") or {})
        headers["Cookie"] = cookie
        ydl_opts["http_headers"] = headers
        return ydl_opts

    cookies_path = cookie_file_path(cookies_file)
    if cookies_path.exists():
        ydl_opts["cookiefile"] = str(cookies_path)
        return ydl_opts

    return ydl_opts


def apply_bilibili_cookie_with_path(
    ydl_opts: dict,
    *,
    cookie_manager,
    cookies_file: str,
    cookie_path: Callable[[], Path],
) -> dict:
    cookie = (cookie_manager.get("bilibili") or "").strip()
    if cookie:
        headers = dict(ydl_opts.get("http_headers") or {})
        headers["Cookie"] = cookie
        ydl_opts["http_headers"] = headers
        return ydl_opts

    cookies_path = cookie_path()
    if cookies_path.exists():
        ydl_opts["cookiefile"] = str(cookies_path)
        return ydl_opts

    return ydl_opts


def extract_flat_playlist(
    space_url: str,
    *,
    limit: int = 0,
    start: Optional[int] = None,
    end: Optional[int] = None,
    infer_platform: Callable[[str], str],
    apply_cookie: Callable[[dict], dict],
    yt_dlp_module=yt_dlp,
) -> dict:
    platform = infer_platform(space_url)
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
        ydl_opts = apply_cookie(ydl_opts)

    with yt_dlp_module.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(space_url, download=False)


def extract_video_metadata(
    video_url: str,
    *,
    apply_cookie: Callable[[dict], dict],
    yt_dlp_module=yt_dlp,
) -> dict:
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
    ydl_opts = apply_cookie(ydl_opts)

    with yt_dlp_module.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(video_url, download=False)


def enrich_missing_titles(
    videos: list[dict],
    *,
    extract_metadata: Callable[[str], dict],
) -> list[dict]:
    missing_title_indexes = [index for index, video in enumerate(videos) if not video.get("title")]
    if not missing_title_indexes:
        return videos

    enriched = [dict(video) for video in videos]
    max_workers = min(8, len(missing_title_indexes))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(extract_metadata, enriched[index]["video_url"]): index
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
            metadata = extract_metadata(enriched[index]["video_url"])
        except Exception:
            continue
        title = (metadata.get("title") or "").strip()
        if title:
            enriched[index]["title"] = title
    return enriched
