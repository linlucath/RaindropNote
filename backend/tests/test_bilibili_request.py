from pathlib import Path

from app.services import bilibili_request


def test_resolve_relative_cookie_path_uses_backend_root_semantics():
    expected_root = Path(bilibili_request.__file__).resolve().parents[2]

    cookies_path = bilibili_request.resolve_bilibili_cookies_path('relative-cookies.txt')

    assert cookies_path == expected_root / 'relative-cookies.txt'


def test_apply_ydl_defaults_sets_request_defaults_and_prefers_existing_cookiefile(tmp_path):
    cookies_file = tmp_path / 'cookies.txt'
    cookies_file.write_text('bilibili cookies', encoding='utf-8')

    ydl_opts = bilibili_request.apply_bilibili_ydl_defaults(
        {},
        cookies_file=cookies_file,
        cookie_getter=lambda platform: 'SESSDATA=config-cookie',
    )

    assert ydl_opts['nocheckcertificate'] is True
    assert ydl_opts['cookiefile'] == str(cookies_file)
    assert 'User-Agent' in ydl_opts['http_headers']
    assert ydl_opts['http_headers']['Referer'] == 'https://www.bilibili.com/'
    assert ydl_opts['http_headers']['Accept-Language'] == 'zh-CN,zh;q=0.9,en;q=0.8'
    assert 'Cookie' not in ydl_opts['http_headers']


def test_apply_ydl_defaults_uses_cookie_header_when_cookiefile_missing(tmp_path):
    missing_cookies_file = tmp_path / 'missing-cookies.txt'

    ydl_opts = bilibili_request.apply_bilibili_ydl_defaults(
        {},
        cookies_file=missing_cookies_file,
        cookie_getter=lambda platform: '  SESSDATA=config-cookie  ',
    )

    assert 'cookiefile' not in ydl_opts
    assert ydl_opts['http_headers']['Cookie'] == 'SESSDATA=config-cookie'


def test_build_uploader_headers_keeps_required_headers_and_adds_cookie():
    headers = bilibili_request.build_bilibili_uploader_headers(
        mid='12345',
        cookie='SESSDATA=uploader-cookie',
    )

    assert headers['Referer'] == 'https://space.bilibili.com/12345/upload/video'
    assert headers['Origin'] == 'https://space.bilibili.com'
    assert headers['Accept'] == 'application/json, text/plain, */*'
    assert headers['Cookie'] == 'SESSDATA=uploader-cookie'
