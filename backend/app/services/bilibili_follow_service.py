from __future__ import annotations

from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import Any, Optional

import requests

FOLLOWINGS_API_URL = 'https://api.bilibili.com/x/relation/followings'


@dataclass
class BilibiliFollowService:
    cookie_getter: Any

    def _get_cookie(self) -> str:
        cookie = (self.cookie_getter('bilibili') or '').strip()
        if not cookie:
            raise ValueError('请先在设置页填写 Bilibili Cookie')
        return cookie

    def _get_self_mid(self, cookie: str) -> str:
        parsed_cookie = SimpleCookie()
        parsed_cookie.load(cookie)
        morsel = parsed_cookie.get('DedeUserID')
        mid = morsel.value.strip() if morsel else ''
        if not mid:
            raise ValueError('Bilibili Cookie 缺少 DedeUserID，请重新登录后更新')
        return mid

    def _build_headers(self, cookie: str) -> dict[str, str]:
        return {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            'Referer': 'https://space.bilibili.com/',
            'Origin': 'https://space.bilibili.com',
            'Accept': 'application/json, text/plain, */*',
            'Cookie': cookie,
        }

    def _normalize_following_item(self, item: dict[str, Any]) -> dict[str, str]:
        return {
            'mid': str(item.get('mid') or ''),
            'name': item.get('uname') or item.get('name') or '',
            'face': item.get('face') or '',
            'sign': item.get('sign') or '',
        }

    def get_followings(self, page: int, page_size: int, keyword: Optional[str] = None) -> dict[str, Any]:
        cookie = self._get_cookie()
        mid = self._get_self_mid(cookie)
        params = {
            'vmid': mid,
            'pn': page,
            'ps': page_size,
            'order': 'desc',
        }
        response = requests.get(
            FOLLOWINGS_API_URL,
            params=params,
            headers=self._build_headers(cookie),
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        code = payload.get('code', -1)
        if code != 0:
            if code in {-101, 22007, 22115}:
                raise ValueError('Bilibili Cookie 已失效，请重新更新')
            raise ValueError(payload.get('message') or payload.get('msg') or '获取关注列表失败')

        data = payload.get('data') or {}
        raw_items = data.get('list') or []
        items = [self._normalize_following_item(item) for item in raw_items]
        normalized_keyword = (keyword or '').strip().lower()
        if normalized_keyword:
            items = [item for item in items if normalized_keyword in item['name'].lower()]

        total = data.get('total')
        if normalized_keyword:
            total = len(items)

        return {
            'items': items,
            'page': page,
            'page_size': page_size,
            'has_more': bool(data.get('total', 0) > page * page_size) if total is not None else False,
            'total': total if total is not None else len(items),
        }
