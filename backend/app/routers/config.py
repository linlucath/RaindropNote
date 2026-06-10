import os

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.bilibili_api_client import BilibiliApiClient
from app.services.bilibili_cookie_parser import extract_bilibili_cookie
from app.services.cookie_manager import CookieConfigManager
from app.utils.response import ResponseWrapper as R
from ffmpeg_helper import ensure_ffmpeg_or_raise

router = APIRouter()
cookie_manager = CookieConfigManager()


class CookieUpdateRequest(BaseModel):
    platform: str
    cookie: str


def validate_bilibili_cookie(cookie: str) -> str:
    client = BilibiliApiClient(
        cookie_getter=lambda _platform: '',
        referer='https://www.bilibili.com/',
        origin='https://www.bilibili.com',
    )
    return client.validate_cookie(cookie)


@router.get("/get_downloader_cookie/{platform}")
def get_cookie(platform: str):
    cookie = cookie_manager.get(platform)
    if not cookie:
        return R.success(msg="未找到Cookies")
    return R.success(data={"platform": platform, "cookie": cookie})


@router.post("/update_downloader_cookie")
def update_cookie(data: CookieUpdateRequest):
    try:
        raw_cookie = (data.cookie or '').strip()
        if data.platform == 'bilibili':
            normalized_cookie = extract_bilibili_cookie(raw_cookie)
            validated_cookie = validate_bilibili_cookie(normalized_cookie)
            cookie_manager.set(data.platform, validated_cookie)
        else:
            cookie_manager.set(data.platform, raw_cookie)
        return R.success()
    except ValueError as exc:
        return R.error(msg=str(exc))


@router.get("/sys_health")
async def sys_health():
    try:
        ensure_ffmpeg_or_raise()
        return R.success()
    except EnvironmentError:
        return R.error(msg="系统未安装 ffmpeg 请先进行安装")


@router.get("/sys_check")
async def sys_check():
    return R.success()


@router.get("/deploy_status")
async def deploy_status():
    """返回部署监控所需的所有状态信息。"""
    import torch

    cuda_available = torch.cuda.is_available()
    cuda_info = {
        "available": cuda_available,
        "version": torch.version.cuda if cuda_available else None,
        "gpu_name": torch.cuda.get_device_name(0) if cuda_available else None,
    }

    try:
        ensure_ffmpeg_or_raise()
        ffmpeg_ok = True
    except Exception:
        ffmpeg_ok = False

    return R.success(
        data={
            "backend": {"status": "running", "port": int(os.getenv("BACKEND_PORT", 8483))},
            "cuda": cuda_info,
            "subtitles": {"mode": "platform_only"},
            "ffmpeg": {"available": ffmpeg_ok},
        }
    )
