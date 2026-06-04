import pytest

from app.services.bilibili_api_client import BilibiliApiClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_get_cookie_requires_configured_bilibili_cookie():
    client = BilibiliApiClient(
        cookie_getter=lambda _platform: '   ',
        referer='https://space.bilibili.com/',
        origin='https://space.bilibili.com',
    )

    with pytest.raises(ValueError, match='请先在设置页填写 Bilibili Cookie'):
        client.get_cookie()


@pytest.mark.parametrize('code', [-101, 22007, 22115])
def test_request_json_normalizes_cookie_invalid_codes(code):
    client = BilibiliApiClient(
        cookie_getter=lambda _platform: 'SESSDATA=test;',
        referer='https://t.bilibili.com/',
        origin='https://www.bilibili.com',
        request_get=lambda *_args, **_kwargs: FakeResponse({'code': code, 'message': 'raw error'}),
    )

    with pytest.raises(ValueError, match='Bilibili Cookie 已失效，请重新更新'):
        client.request_json('https://api.bilibili.com/example', fallback_error='获取关注动态失败')


def test_request_json_keeps_required_headers_and_uses_injected_request_get():
    calls = []

    def request_get(url, **kwargs):
        calls.append({'url': url, **kwargs})
        return FakeResponse({'code': 0, 'data': {'ok': True}})

    client = BilibiliApiClient(
        cookie_getter=lambda _platform: '  SESSDATA=test; DedeUserID=12345;  ',
        referer='https://space.bilibili.com/',
        origin='https://space.bilibili.com',
        request_get=request_get,
    )

    payload = client.request_json(
        'https://api.bilibili.com/example',
        params={'pn': 1},
        fallback_error='获取关注列表失败',
    )

    assert payload == {'code': 0, 'data': {'ok': True}}
    assert calls == [
        {
            'url': 'https://api.bilibili.com/example',
            'params': {'pn': 1},
            'headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/124.0.0.0 Safari/537.36'
                ),
                'Referer': 'https://space.bilibili.com/',
                'Origin': 'https://space.bilibili.com',
                'Accept': 'application/json, text/plain, */*',
                'Cookie': 'SESSDATA=test; DedeUserID=12345;',
            },
            'timeout': 15,
        }
    ]


def test_request_json_uses_payload_message_for_other_bilibili_errors():
    client = BilibiliApiClient(
        cookie_getter=lambda _platform: 'SESSDATA=test;',
        referer='https://space.bilibili.com/',
        origin='https://space.bilibili.com',
        request_get=lambda *_args, **_kwargs: FakeResponse({'code': -400, 'message': '请求错误'}),
    )

    with pytest.raises(ValueError, match='请求错误'):
        client.request_json('https://api.bilibili.com/example', fallback_error='获取关注列表失败')


def test_request_json_allows_custom_headers_and_business_error_messages():
    calls = []

    def request_get(url, **kwargs):
        calls.append({'url': url, **kwargs})
        return FakeResponse({'code': -352, 'message': 'raw risk error'})

    client = BilibiliApiClient(
        cookie_getter=lambda _platform: '',
        referer='https://space.bilibili.com/',
        origin='https://space.bilibili.com',
        request_get=request_get,
    )

    with pytest.raises(ValueError, match='Bilibili 接口触发风控，请稍后重试'):
        client.request_json(
            'https://api.bilibili.com/example',
            fallback_error='获取 UP 主视频失败',
            headers={'X-Test': 'custom'},
            error_messages_by_code={-352: 'Bilibili 接口触发风控，请稍后重试'},
        )

    assert calls == [
        {
            'url': 'https://api.bilibili.com/example',
            'headers': {'X-Test': 'custom'},
            'params': None,
            'timeout': 15,
        }
    ]
