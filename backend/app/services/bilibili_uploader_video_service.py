from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from app.services.bilibili_api_client import BilibiliApiClient
from app.services.bilibili_uploader_items import normalize_uploader_video_item
from app.services.bilibili_wbi import (
    WBI_MIXIN_KEY_ENC_TAB,
    build_signed_wbi_params,
    extract_wbi_mixin_key,
)

NAV_API_URL = 'https://api.bilibili.com/x/web-interface/nav'
UPLOADER_VIDEOS_API_URL = 'https://api.bilibili.com/x/space/wbi/arc/search'
UPLOADER_RISK_CONTROL_CODES = {-352, -412}
UPLOADER_BUSINESS_ERROR_MESSAGES = {
    code: 'Bilibili 接口触发风控，请稍后重试' for code in UPLOADER_RISK_CONTROL_CODES
}
@dataclass
class BilibiliUploaderVideoService:
    cookie_getter: Any

    def _request_get(self, url: str, **kwargs: Any) -> Any:
        return requests.get(url, **kwargs)

    def _api_client(self, mid: str) -> BilibiliApiClient:
        return BilibiliApiClient(
            cookie_getter=self.cookie_getter,
            referer=f'https://space.bilibili.com/{mid}/upload/video',
            origin='https://space.bilibili.com',
            request_get=self._request_get,
        )

    def _get_cookie(self) -> str:
        return self._api_client(mid='').get_cookie()

    def _build_headers(self, mid: str, cookie: str) -> dict[str, str]:
        return self._api_client(mid=mid).build_headers(cookie)

    def _get_wbi_mixin_key(self, mid: str, headers: dict[str, str]) -> str:
        payload = self._api_client(mid=mid).request_json(
            NAV_API_URL,
            headers=headers,
            fallback_error='获取 Bilibili WBI 签名失败',
        )
        return extract_wbi_mixin_key(payload)

    def _sign_params(self, mid: str, params: dict[str, Any], headers: dict[str, str]) -> dict[str, str]:
        mixin_key = self._get_wbi_mixin_key(mid=mid, headers=headers)
        return build_signed_wbi_params(params, mixin_key=mixin_key)

    def _normalize_video_item(self, item: dict[str, Any]) -> dict[str, str] | None:
        return normalize_uploader_video_item(item)

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
        payload = self._api_client(mid=mid).request_json(
            UPLOADER_VIDEOS_API_URL,
            params=params,
            headers=headers,
            fallback_error='获取创作者视频失败',
            error_messages_by_code=UPLOADER_BUSINESS_ERROR_MESSAGES,
        )
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
