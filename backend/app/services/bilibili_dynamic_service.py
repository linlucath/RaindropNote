from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

DYNAMICS_API_URL = 'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all'
DYNAMICS_FEATURES = (
    'itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote,decorationCard,'
    'onlyfansAssetsV2,forwardListHidden,ugcDelete'
)


@dataclass
class BilibiliDynamicService:
    cookie_getter: Any

    def _get_cookie(self) -> str:
        cookie = (self.cookie_getter('bilibili') or '').strip()
        if not cookie:
            raise ValueError('请先在设置页填写 Bilibili Cookie')
        return cookie

    def _build_headers(self, cookie: str) -> dict[str, str]:
        return {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            'Referer': 'https://t.bilibili.com/',
            'Origin': 'https://www.bilibili.com',
            'Accept': 'application/json, text/plain, */*',
            'Cookie': cookie,
        }

    def _normalize_video_dynamic(self, item: dict[str, Any]) -> dict[str, str] | None:
        if item.get('type') != 'DYNAMIC_TYPE_AV':
            return None

        modules = item.get('modules') or {}
        module_dynamic = modules.get('module_dynamic') or {}
        major = module_dynamic.get('major') or {}
        if major.get('type') != 'MAJOR_TYPE_ARCHIVE':
            return None

        archive = major.get('archive') or {}
        bvid = str(archive.get('bvid') or '').strip()
        if not bvid:
            return None

        jump_url = str(archive.get('jump_url') or '').strip()
        if jump_url.startswith('//'):
            video_url = f'https:{jump_url}'
        elif jump_url.startswith('http://') or jump_url.startswith('https://'):
            video_url = jump_url
        else:
            video_url = f'https://www.bilibili.com/video/{bvid}/'

        module_author = modules.get('module_author') or {}
        author_name = (
            module_author.get('name')
            or module_author.get('uname')
            or module_author.get('nickname')
            or ''
        )

        return {
            'video_id': bvid,
            'video_url': video_url,
            'title': str(archive.get('title') or archive.get('desc') or '').strip(),
            'author_name': str(author_name).strip(),
            'dynamic_id': str(item.get('id_str') or '').strip(),
            'cover': str(archive.get('cover') or '').strip(),
        }

    def _request_dynamics_page(self, cookie: str, offset: str | None) -> dict[str, Any]:
        params = {
            'type': 'video',
            'platform': 'web',
            'features': DYNAMICS_FEATURES,
            'web_location': '333.1365',
        }
        if offset:
            params['offset'] = offset

        response = requests.get(
            DYNAMICS_API_URL,
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
            raise ValueError(payload.get('message') or payload.get('msg') or '获取关注动态失败')
        return payload.get('data') or {}

    def get_video_dynamics(self, page_size: int, offset: str | None) -> dict[str, Any]:
        cookie = self._get_cookie()
        collected: list[dict[str, str]] = []
        collected_dynamic_ids: list[str] = []
        seen_video_ids: set[str] = set()
        next_request_offset = offset or ''
        has_more_raw = False

        for _ in range(10):
            data = self._request_dynamics_page(cookie=cookie, offset=next_request_offset or None)
            items = data.get('items') or []
            has_more_raw = bool(data.get('has_more'))
            next_request_offset = str(data.get('offset') or '').strip()

            if not items:
                break

            for item in items:
                normalized = self._normalize_video_dynamic(item)
                if not normalized:
                    continue

                video_id = normalized['video_id']
                if video_id in seen_video_ids:
                    continue

                seen_video_ids.add(video_id)
                collected.append(normalized)
                collected_dynamic_ids.append(normalized['dynamic_id'])

                if len(collected) >= page_size + 1:
                    visible_items = collected[:page_size]
                    last_visible_dynamic_id = collected_dynamic_ids[page_size - 1]
                    return {
                        'items': visible_items,
                        'offset': last_visible_dynamic_id,
                        'page_size': page_size,
                        'has_more': True,
                    }

            if not has_more_raw or not next_request_offset:
                break

        return {
            'items': collected[:page_size],
            'offset': next_request_offset if has_more_raw else '',
            'page_size': page_size,
            'has_more': False,
        }
