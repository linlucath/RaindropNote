from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import requests

BILIBILI_COOKIE_INVALID_CODES = {-101, 22007, 22115}
BILIBILI_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)


def _default_request_get(url: str, **kwargs: Any) -> Any:
    return requests.get(url, **kwargs)


@dataclass
class BilibiliApiClient:
    cookie_getter: Callable[[str], str | None]
    referer: str
    origin: str
    request_get: Callable[..., Any] | None = None

    def get_cookie(self) -> str:
        cookie = (self.cookie_getter('bilibili') or '').strip()
        if not cookie:
            raise ValueError('请先在设置页填写 Bilibili Cookie')
        return cookie

    def build_headers(self, cookie: str | None = None) -> dict[str, str]:
        active_cookie = self.get_cookie() if cookie is None else cookie
        return {
            'User-Agent': BILIBILI_USER_AGENT,
            'Referer': self.referer,
            'Origin': self.origin,
            'Accept': 'application/json, text/plain, */*',
            'Cookie': active_cookie,
        }

    def request_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        fallback_error: str,
        cookie: str | None = None,
        headers: dict[str, str] | None = None,
        error_messages_by_code: dict[int, str] | None = None,
    ) -> dict[str, Any]:
        active_cookie = self.get_cookie() if cookie is None and headers is None else cookie
        active_headers = headers if headers is not None else self.build_headers(active_cookie)
        request_get = self.request_get or _default_request_get
        response = request_get(
            url,
            params=params,
            headers=active_headers,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        code = payload.get('code', -1)
        if code != 0:
            if code in BILIBILI_COOKIE_INVALID_CODES:
                raise ValueError('Bilibili Cookie 已失效，请重新更新')
            if error_messages_by_code and code in error_messages_by_code:
                raise ValueError(error_messages_by_code[code])
            raise ValueError(payload.get('message') or payload.get('msg') or fallback_error)
        return payload
