import logging
from typing import Optional

import requests

from app.utils.video_url_rules import (
    extract_video_id_from_url,
    infer_platform_from_url as infer_platform_from_http_url,
)

logger = logging.getLogger(__name__)


def infer_platform_from_url(url: str) -> Optional[str]:
    """
    根据 http(s) 视频链接推断平台。

    非 http(s) 的本地路径不自动推断，仍由调用方显式传入 platform。
    """
    return infer_platform_from_http_url(url)


def extract_video_id(url: str, platform: str) -> Optional[str]:
    """
    从视频链接中提取视频 ID

    :param url: 视频链接
    :param platform: 平台名（bilibili / youtube / douyin）
    :return: 提取到的视频 ID 或 None
    """
    if platform == "bilibili":
        # 如果是短链接，则解析真实链接
        if "b23.tv" in url:
            resolved_url = resolve_bilibili_short_url(url)
            if resolved_url:
                url = resolved_url

    return extract_video_id_from_url(url, platform)


def resolve_bilibili_short_url(short_url: str) -> Optional[str]:
    """
    解析哔哩哔哩短链接以获取真实视频链接

    :param short_url: Bilibili短链接（如"https://b23.tv/xxxxxx"）
    :return: 真实的视频链接或None
    """
    try:
        response = requests.head(short_url, allow_redirects=True)
        return response.url
    except requests.RequestException as e:
        logger.warning("Error resolving short URL: %s", e)
        return None
