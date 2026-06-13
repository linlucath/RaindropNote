from __future__ import annotations

import re
import shlex


def _normalize_cookie_string(cookie_text: str) -> str:
    parts: list[str] = []
    for raw_part in cookie_text.split(';'):
        part = raw_part.strip()
        if not part or '=' not in part:
            continue
        key, value = part.split('=', 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        parts.append(f'{key}={value}')
    return '; '.join(parts)


def _extract_cookie_from_header_text(text: str) -> str | None:
    match = re.search(r'(?im)^\s*cookie\s*:\s*(.+?)\s*$', text)
    if not match:
        return None
    return match.group(1).strip()


def _extract_cookie_from_curl(text: str) -> str | None:
    if 'curl' not in text:
        return None

    try:
        argv = shlex.split(text)
    except ValueError:
        argv = []

    for index, token in enumerate(argv):
        if token not in {'-H', '--header'}:
            continue
        if index + 1 >= len(argv):
            continue
        header_value = argv[index + 1]
        if header_value.lower().startswith('cookie:'):
            return header_value.split(':', 1)[1].strip()

    return None


def extract_bilibili_cookie(text: str) -> str:
    raw_text = (text or '').strip()
    if not raw_text:
        raise ValueError('未从输入内容中提取到 Bilibili Cookie')

    extracted = (
        _extract_cookie_from_header_text(raw_text)
        or _extract_cookie_from_curl(raw_text)
        or raw_text
    )
    normalized = _normalize_cookie_string(extracted)
    if not normalized:
        raise ValueError('未从输入内容中提取到 Bilibili Cookie')
    return normalized
