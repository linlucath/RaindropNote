from urllib.parse import urlencode
import hashlib

from app.services.bilibili_uploader_items import normalize_uploader_video_item
from app.services.bilibili_wbi import build_signed_wbi_params, extract_wbi_mixin_key


def test_normalize_uploader_video_item_preserves_legacy_url_and_count_rules():
    assert normalize_uploader_video_item(
        {
            'bvid': ' BV111 ',
            'jump_url': '//www.bilibili.com/video/BV111/',
            'title': '  first video  ',
            'play': '123',
        }
    ) == {
        'video_id': 'BV111',
        'video_url': 'https://www.bilibili.com/video/BV111/',
        'title': 'first video',
        'view_count': 123,
    }

    assert normalize_uploader_video_item({'bvid': 'BV222', 'title': 'second'}) == {
        'video_id': 'BV222',
        'video_url': 'https://www.bilibili.com/video/BV222',
        'title': 'second',
        'view_count': 0,
    }
    assert normalize_uploader_video_item({'bvid': '   '}) is None


def test_extract_wbi_mixin_key_uses_bilibili_lookup_table():
    payload = {
        'data': {
            'wbi_img': {
                'img_url': 'https://i0.hdslb.com/bfs/wbi/abcdefghijklmnopqrstuvwxyzabcdef.png',
                'sub_url': 'https://i0.hdslb.com/bfs/wbi/01234567890123456789012345678901.png',
            }
        }
    }

    assert extract_wbi_mixin_key(payload) == '45sc1ix0p8kf6d33b1f71j0tdco7m69n'


def test_build_signed_wbi_params_sorts_sanitizes_and_signs_params():
    params = {'mid': '12345', 'keyword': "bad!'()*chars", 'pn': 1}

    signed = build_signed_wbi_params(params, mixin_key='0' * 32, wts=1_717_000_000)

    expected_unsigned = {
        'keyword': 'badchars',
        'mid': '12345',
        'pn': '1',
        'wts': '1717000000',
    }
    expected_query = urlencode(expected_unsigned)
    assert signed == {
        **expected_unsigned,
        'w_rid': hashlib.md5(f'{expected_query}{"0" * 32}'.encode()).hexdigest(),
    }
