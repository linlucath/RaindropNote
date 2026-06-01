from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time
from typing import Any
from urllib.parse import urlencode

import requests

NAV_API_URL = 'https://api.bilibili.com/x/web-interface/nav'
UPLOADER_VIDEOS_API_URL = 'https://api.bilibili.com/x/space/wbi/arc/search'
WBI_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]


@dataclass
class BilibiliUploaderVideoService:
    cookie_getter: Any

    def _get_cookie(self) -> str:
        return (self.cookie_getter('bilibili') or '').strip()

    def _build_headers(self, mid: str, cookie: str) -> dict[str, str]:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            'Referer': f'https://space.bilibili.com/{mid}/upload/video',
            'Origin': 'https://space.bilibili.com',
            'Accept': 'application/json, text/plain, */*',
        }
        if cookie:
            headers['Cookie'] = cookie
        return headers

    def _get_wbi_mixin_key(self, mid: str, headers: dict[str, str]) -> str:
        response = requests.get(NAV_API_URL, headers=headers, timeout=15)
        response.raise_for_status()
        payload = response.json()
        if payload.get('code', -1) != 0:
            raise ValueError(payload.get('message') or payload.get('msg') or '获取 Bilibili WBI 签名失败')

        wbi_img = (payload.get('data') or {}).get('wbi_img') or {}
        img_key = str(wbi_img.get('img_url') or '').rsplit('/', 1)[-1].split('.')[0]
        sub_key = str(wbi_img.get('sub_url') or '').rsplit('/', 1)[-1].split('.')[0]
        lookup = img_key + sub_key
        if not lookup:
            raise ValueError('获取 Bilibili WBI 签名失败')

        return ''.join(lookup[index] for index in WBI_MIXIN_KEY_ENC_TAB)[:32]

    def _sign_params(self, mid: str, params: dict[str, Any], headers: dict[str, str]) -> dict[str, str]:
        mixin_key = self._get_wbi_mixin_key(mid=mid, headers=headers)
        signed_params = {
            key: ''.join(char for char in str(value) if char not in "!'()*")
            for key, value in sorted({**params, 'wts': round(time.time())}.items())
        }
        query = urlencode(signed_params)
        signed_params['w_rid'] = hashlib.md5(f'{query}{mixin_key}'.encode()).hexdigest()
        return signed_params

    def _normalize_video_item(self, item: dict[str, Any]) -> dict[str, str] | None:
        bvid = str(item.get('bvid') or '').strip()
        if not bvid:
            return None

        jump_url = str(item.get('jump_url') or '').strip()
        if jump_url.startswith('//'):
            video_url = f'https:{jump_url}'
        elif jump_url.startswith('http://') or jump_url.startswith('https://'):
            video_url = jump_url
        else:
            video_url = f'https://www.bilibili.com/video/{bvid}'

        return {
            'video_id': bvid,
            'video_url': video_url,
            'title': str(item.get('title') or '').strip(),
            'view_count': int(item.get('play') or 0),
        }

    def _request_uploader_videos_page(
        self,
        mid: str,
        page: int,
        page_size: int,
        order: str,
    ) -> dict[str, Any]:
        cookie = self._get_cookie()
        headers = self._build_headers(mid=mid, cookie=cookie)
        params = self._sign_params(
            mid=mid,
            headers=headers,
            params={
                'pn': page,
                'ps': page_size,
                'tid': 0,
                'order': order,
                'mid': mid,
                'keyword': '',
                'order_avoided': 'true',
                'platform': 'web',
            },
        )
        response = requests.get(
            UPLOADER_VIDEOS_API_URL,
            params=params,
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        code = payload.get('code', -1)
        if code != 0:
            if code in {-101, 22007, 22115}:
                raise ValueError('Bilibili Cookie 已失效，请重新更新')
            if code in {-352, -412}:
                raise ValueError('Bilibili 接口触发风控，请稍后重试')
            raise ValueError(payload.get('message') or payload.get('msg') or '获取 UP 主视频失败')
        return payload.get('data') or {}

    def get_uploader_videos_page(
        self,
        mid: str,
        page: int,
        page_size: int,
        limit: int = 0,
        order: str = 'click',
    ) -> dict[str, Any]:
        start = (page - 1) * page_size + 1
        if limit > 0 and start > limit:
            return {
                'items': [],
                'page': page,
                'page_size': page_size,
                'has_more': False,
                'total': limit,
            }

        extra_probe = 1
        if limit > 0:
            remaining = limit - start + 1
            fetch_size = max(min(page_size + extra_probe, remaining), 0)
        else:
            fetch_size = page_size + extra_probe

        if fetch_size <= 0:
            return {
                'items': [],
                'page': page,
                'page_size': page_size,
                'has_more': False,
                'total': limit if limit > 0 else None,
            }

        data = self._request_uploader_videos_page(
            mid=mid,
            page=page,
            page_size=fetch_size,
            order=order,
        )
        raw_items = ((data.get('list') or {}).get('vlist') or [])
        items = [
            normalized
            for normalized in (self._normalize_video_item(item) for item in raw_items)
            if normalized
        ][:fetch_size]
        has_more = len(items) > page_size
        return {
            'items': items[:page_size],
            'page': page,
            'page_size': page_size,
            'has_more': has_more,
            'total': limit if limit > 0 else None,
        }
