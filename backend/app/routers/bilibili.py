from fastapi import APIRouter, Query

from app.routers.batch import mark_processed_page_items, preview_bilibili_space_page
from app.services.bilibili_dynamic_service import BilibiliDynamicService
from app.services.bilibili_follow_service import BilibiliFollowService
from app.services.cookie_manager import CookieConfigManager
from app.utils.response import ResponseWrapper as R

router = APIRouter()
cookie_manager = CookieConfigManager()
follow_service = BilibiliFollowService(cookie_manager.get)
dynamic_service = BilibiliDynamicService(cookie_manager.get)


def build_uploader_space_url(mid: str) -> str:
    return f'https://space.bilibili.com/{mid}/upload/video'


@router.get('/bilibili/followings')
def get_followings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    try:
        data = follow_service.get_followings(page=page, page_size=page_size)
    except ValueError as exc:
        return R.error(msg=str(exc))
    except Exception as exc:  # pragma: no cover - defensive fallback
        return R.error(msg=f'获取关注列表失败: {exc}')
    return R.success(data=data)


@router.get('/bilibili/uploader_videos')
def get_uploader_videos(
    mid: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    limit: int = Query(default=20, ge=0, le=500),
):
    try:
        videos = preview_bilibili_space_page(
            build_uploader_space_url(mid),
            page=page,
            page_size=page_size,
            limit=limit,
        )
    except Exception as exc:  # pragma: no cover - passthrough for runtime failures
        return R.error(msg=f'获取创作者视频失败: {exc}')
    return R.success(data=videos)


@router.get('/bilibili/dynamics')
def get_followed_dynamics(
    offset: str | None = Query(default=None),
    page_size: int = Query(default=20, ge=1, le=50),
):
    try:
        data = dynamic_service.get_video_dynamics(page_size=page_size, offset=offset)
    except ValueError as exc:
        return R.error(msg=str(exc))
    except Exception as exc:  # pragma: no cover - defensive fallback
        return R.error(msg=f'获取关注动态失败: {exc}')
    return R.success(data=mark_processed_page_items(data))
