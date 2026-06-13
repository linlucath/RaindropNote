import pytest

from app.services.bilibili_cookie_parser import extract_bilibili_cookie


def test_extract_bilibili_cookie_accepts_raw_cookie_text():
    cookie = extract_bilibili_cookie('  SESSDATA=test; DedeUserID=12345; bili_jct=csrf  ')

    assert cookie == 'SESSDATA=test; DedeUserID=12345; bili_jct=csrf'


def test_extract_bilibili_cookie_accepts_cookie_header_line():
    cookie = extract_bilibili_cookie('Cookie: SESSDATA=test; DedeUserID=12345; bili_jct=csrf')

    assert cookie == 'SESSDATA=test; DedeUserID=12345; bili_jct=csrf'


def test_extract_bilibili_cookie_accepts_curl_header_snippet():
    cookie = extract_bilibili_cookie(
        "curl 'https://api.bilibili.com/x/web-interface/nav' "
        "-H 'Cookie: SESSDATA=test; DedeUserID=12345; bili_jct=csrf'"
    )

    assert cookie == 'SESSDATA=test; DedeUserID=12345; bili_jct=csrf'


def test_extract_bilibili_cookie_rejects_text_without_cookie_content():
    with pytest.raises(ValueError, match='未从输入内容中提取到 Bilibili Cookie'):
        extract_bilibili_cookie('hello world')
