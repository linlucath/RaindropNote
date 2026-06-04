from __future__ import annotations

import hashlib
import time
from typing import Any
from urllib.parse import urlencode


WBI_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]


def extract_wbi_mixin_key(payload: dict[str, Any]) -> str:
    wbi_img = (payload.get('data') or {}).get('wbi_img') or {}
    img_key = str(wbi_img.get('img_url') or '').rsplit('/', 1)[-1].split('.')[0]
    sub_key = str(wbi_img.get('sub_url') or '').rsplit('/', 1)[-1].split('.')[0]
    lookup = img_key + sub_key
    if not lookup:
        raise ValueError('获取 Bilibili WBI 签名失败')

    return ''.join(lookup[index] for index in WBI_MIXIN_KEY_ENC_TAB)[:32]


def build_signed_wbi_params(
    params: dict[str, Any],
    *,
    mixin_key: str,
    wts: int | None = None,
) -> dict[str, str]:
    signing_time = round(time.time()) if wts is None else wts
    signed_params = {
        key: ''.join(char for char in str(value) if char not in "!'()*")
        for key, value in sorted({**params, 'wts': signing_time}.items())
    }
    query = urlencode(signed_params)
    signed_params['w_rid'] = hashlib.md5(f'{query}{mixin_key}'.encode()).hexdigest()
    return signed_params
