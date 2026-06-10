import json

from app.routers import config as config_router


def _json_body(response):
    return json.loads(response.body.decode('utf-8'))


def test_update_cookie_for_bilibili_extracts_validates_and_saves(monkeypatch):
    saved = []
    validated = []

    monkeypatch.setattr(
        config_router,
        'extract_bilibili_cookie',
        lambda text: 'SESSDATA=test; DedeUserID=12345; bili_jct=csrf',
        raising=False,
    )
    monkeypatch.setattr(
        config_router,
        'validate_bilibili_cookie',
        lambda cookie: validated.append(cookie) or cookie,
        raising=False,
    )
    monkeypatch.setattr(
        config_router.cookie_manager,
        'set',
        lambda platform, cookie: saved.append((platform, cookie)),
    )

    response = config_router.update_cookie(
        config_router.CookieUpdateRequest(
            platform='bilibili',
            cookie="curl -H 'Cookie: SESSDATA=test; DedeUserID=12345'",
        )
    )

    assert validated == ['SESSDATA=test; DedeUserID=12345; bili_jct=csrf']
    assert saved == [('bilibili', 'SESSDATA=test; DedeUserID=12345; bili_jct=csrf')]
    assert _json_body(response)['code'] == 0


def test_update_cookie_for_bilibili_returns_error_when_cookie_is_invalid(monkeypatch):
    monkeypatch.setattr(
        config_router,
        'extract_bilibili_cookie',
        lambda _text: (_ for _ in ()).throw(ValueError('未从输入内容中提取到 Bilibili Cookie')),
        raising=False,
    )

    response = config_router.update_cookie(
        config_router.CookieUpdateRequest(
            platform='bilibili',
            cookie='not a cookie',
        )
    )

    body = _json_body(response)
    assert body['code'] == 500
    assert body['msg'] == '未从输入内容中提取到 Bilibili Cookie'


def test_update_cookie_for_non_bilibili_keeps_trimmed_save_behavior(monkeypatch):
    saved = []
    monkeypatch.setattr(
        config_router.cookie_manager,
        'set',
        lambda platform, cookie: saved.append((platform, cookie)),
    )

    response = config_router.update_cookie(
        config_router.CookieUpdateRequest(
            platform='youtube',
            cookie='  SID=abc123  ',
        )
    )

    assert saved == [('youtube', 'SID=abc123')]
    assert _json_body(response)['code'] == 0
