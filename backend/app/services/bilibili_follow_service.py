from __future__ import annotations

from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any

import requests

from app.services.bilibili_api_client import BilibiliApiClient

FOLLOWINGS_API_URL = 'https://api.bilibili.com/x/relation/followings'


@dataclass
class BilibiliFollowService:
    cookie_getter: Any
    request_get: Any | None = None

    def _request_get(self, url: str, **kwargs: Any) -> Any:
        return requests.get(url, **kwargs)

    def _api_client(self) -> BilibiliApiClient:
        return BilibiliApiClient(
            cookie_getter=self.cookie_getter,
            referer='https://space.bilibili.com/',
            origin='https://space.bilibili.com',
            request_get=self.request_get or self._request_get,
        )

    def _get_cookie(self) -> str:
        return self._api_client().get_cookie()

    def _get_self_mid(self, cookie: str) -> str:
        parsed_cookie = SimpleCookie()
        parsed_cookie.load(cookie)
        morsel = parsed_cookie.get('DedeUserID')
        mid = morsel.value.strip() if morsel else ''
        if not mid:
            raise ValueError('Bilibili Cookie 缺少 DedeUserID，请重新登录后更新')
        return mid

    def _build_headers(self, cookie: str) -> dict[str, str]:
        return self._api_client().build_headers(cookie)

    def _normalize_avatar_url(self, url: Any) -> str:
        avatar_url = str(url or '').strip()
        if not avatar_url:
            return ''
        if avatar_url.startswith('//'):
            avatar_url = f'https:{avatar_url}'
        elif avatar_url.startswith('http://'):
            avatar_url = f'https://{avatar_url.removeprefix("http://")}'
        if '@' in avatar_url.rsplit('/', 1)[-1]:
            return avatar_url
        return f'{avatar_url}@96w_96h_1c_1s.webp'

    def _normalize_following_item(self, item: dict[str, Any]) -> dict[str, str]:
        return {
            'mid': str(item.get('mid') or ''),
            'name': item.get('uname') or item.get('name') or '',
            'avatar_url': self._normalize_avatar_url(item.get('face') or item.get('avatar_url')),
            'sign': item.get('sign') or '',
        }

    def get_followings(self, page: int, page_size: int) -> dict[str, Any]:
        cookie = self._get_cookie()
        mid = self._get_self_mid(cookie)
        params = {
            'vmid': mid,
            'pn': page,
            'ps': page_size,
            'order': 'desc',
        }
        payload = self._api_client().request_json(
            FOLLOWINGS_API_URL,
            params=params,
            fallback_error='获取关注列表失败',
            cookie=cookie,
        )

        data = payload.get('data') or {}
        raw_items = data.get('list') or []
        items = [self._normalize_following_item(item) for item in raw_items]
        total = data.get('total')

        return {
            'items': items,
            'page': page,
            'page_size': page_size,
            'has_more': bool(data.get('total', 0) > page * page_size) if total is not None else False,
            'total': total if total is not None else len(items),
        }
