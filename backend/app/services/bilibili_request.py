from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BILIBILI_COOKIES_FILE = os.getenv('BILIBILI_COOKIES_FILE', 'cookies.txt')
BILIBILI_YDL_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://www.bilibili.com/',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}
BILIBILI_UPLOADER_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Origin': 'https://space.bilibili.com',
    'Accept': 'application/json, text/plain, */*',
}


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_bilibili_cookies_path(cookies_file: str | Path | None = None) -> Path:
    cookies_path = Path(cookies_file or BILIBILI_COOKIES_FILE)
    if not cookies_path.is_absolute():
        cookies_path = _backend_root() / cookies_path
    return cookies_path


def apply_bilibili_ydl_defaults(
    ydl_opts: dict[str, Any],
    *,
    cookies_file: str | Path | None = None,
    cookie_getter: Callable[[str], str | None] | None = None,
    request_logger: logging.Logger | None = None,
) -> dict[str, Any]:
    active_logger = request_logger or logger
    ydl_opts.setdefault('nocheckcertificate', True)
    ydl_opts.setdefault('http_headers', dict(BILIBILI_YDL_HEADERS))

    cookies_path = resolve_bilibili_cookies_path(cookies_file)
    if cookies_path.exists():
        ydl_opts['cookiefile'] = str(cookies_path)
        active_logger.info(f'使用 cookies 文件: {cookies_path}')
    else:
        raw_cookie = (cookie_getter('bilibili') if cookie_getter else None) or ''
        raw_cookie = raw_cookie.strip()
        if raw_cookie:
            ydl_opts['http_headers'] = {
                **ydl_opts.get('http_headers', {}),
                'Cookie': raw_cookie,
            }
            active_logger.info('使用配置中的 B站 Cookie')
        else:
            active_logger.warning(f'B站 cookies 文件不存在: {cookies_path}，且未配置 B站 Cookie，下载可能失败')

    return ydl_opts


def build_bilibili_uploader_headers(mid: str, cookie: str) -> dict[str, str]:
    headers = {
        **BILIBILI_UPLOADER_HEADERS,
        'Referer': f'https://space.bilibili.com/{mid}/upload/video',
    }
    if cookie:
        headers['Cookie'] = cookie
    return headers
