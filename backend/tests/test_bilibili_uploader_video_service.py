import pytest

from app.services import bilibili_uploader_video_service as uploader_module
from app.services.bilibili_uploader_video_service import (
    UPLOADER_VIDEOS_API_URL,
    BilibiliUploaderVideoService,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_get_uploader_videos_page_requires_configured_cookie_before_network(monkeypatch):
    def request_get(*_args, **_kwargs):
        raise AssertionError('network should not be called without a configured cookie')

    monkeypatch.setattr(uploader_module.requests, 'get', request_get)
    service = BilibiliUploaderVideoService(cookie_getter=lambda _platform: '   ')

    with pytest.raises(ValueError, match='请先在设置页填写 Bilibili Cookie'):
        service.get_uploader_videos_page(mid='12345', page=1, page_size=20)


def test_get_uploader_videos_page_normalizes_cookie_invalid_code(monkeypatch):
    calls = []
    service = BilibiliUploaderVideoService(cookie_getter=lambda _platform: 'SESSDATA=test;')
    monkeypatch.setattr(service, '_get_wbi_mixin_key', lambda *_args, **_kwargs: '0' * 32)

    def request_get(url, **kwargs):
        calls.append({'url': url, **kwargs})
        return FakeResponse({'code': -101, 'message': 'raw cookie error'})

    monkeypatch.setattr(uploader_module.requests, 'get', request_get)

    with pytest.raises(ValueError, match='Bilibili Cookie 已失效，请重新更新'):
        service.get_uploader_videos_page(mid='12345', page=1, page_size=20)

    assert calls[0]['url'] == UPLOADER_VIDEOS_API_URL
    assert calls[0]['headers']['Cookie'] == 'SESSDATA=test;'


def test_get_uploader_videos_page_normalizes_success_payload(monkeypatch):
    calls = []
    service = BilibiliUploaderVideoService(
        cookie_getter=lambda _platform: '  SESSDATA=test; DedeUserID=12345;  '
    )
    monkeypatch.setattr(service, '_get_wbi_mixin_key', lambda *_args, **_kwargs: '0' * 32)

    def request_get(url, **kwargs):
        calls.append({'url': url, **kwargs})
        return FakeResponse(
            {
                'code': 0,
                'data': {
                    'list': {
                        'vlist': [
                            {
                                'bvid': 'BV111',
                                'jump_url': '//www.bilibili.com/video/BV111/',
                                'title': '  first video  ',
                                'play': '123',
                            },
                            {
                                'bvid': 'BV222',
                                'jump_url': 'https://www.bilibili.com/video/BV222/?p=1',
                                'title': 'second video',
                                'play': 0,
                            },
                            {
                                'bvid': 'BV333',
                                'title': 'third video',
                                'play': None,
                            },
                        ]
                    }
                },
            }
        )

    monkeypatch.setattr(uploader_module.requests, 'get', request_get)

    result = service.get_uploader_videos_page(mid='12345', page=1, page_size=2)

    assert result == {
        'items': [
            {
                'video_id': 'BV111',
                'video_url': 'https://www.bilibili.com/video/BV111/',
                'title': 'first video',
                'view_count': 123,
            },
            {
                'video_id': 'BV222',
                'video_url': 'https://www.bilibili.com/video/BV222/?p=1',
                'title': 'second video',
                'view_count': 0,
            },
        ],
        'page': 1,
        'page_size': 2,
        'has_more': True,
        'total': None,
    }
    assert calls[0]['url'] == UPLOADER_VIDEOS_API_URL
    assert calls[0]['headers'] == {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        ),
        'Referer': 'https://space.bilibili.com/12345/upload/video',
        'Origin': 'https://space.bilibili.com',
        'Accept': 'application/json, text/plain, */*',
        'Cookie': 'SESSDATA=test; DedeUserID=12345;',
    }
