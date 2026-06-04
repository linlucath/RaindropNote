from typing import Callable


def preview_space_page(
    space_url: str,
    page: int,
    page_size: int,
    limit: int,
    *,
    infer_platform: Callable[[str], str],
    preview_youtube_popular: Callable[..., dict],
    preview_youtube_fallback: Callable[..., dict],
    parse_bilibili_space_request: Callable[[str], tuple[str | None, str]],
    uploader_video_service,
    preview_bilibili_flat: Callable[..., dict],
) -> dict:
    if infer_platform(space_url) == "youtube":
        try:
            return preview_youtube_popular(
                space_url=space_url,
                page=page,
                page_size=page_size,
                limit=limit,
            )
        except Exception:
            pass
        return preview_youtube_fallback(space_url, page=page, page_size=page_size, limit=limit)

    mid, order = parse_bilibili_space_request(space_url)
    if mid:
        return uploader_video_service.get_uploader_videos_page(
            mid=mid,
            page=page,
            page_size=page_size,
            limit=limit,
            order=order,
        )

    return preview_bilibili_flat(space_url, page=page, page_size=page_size, limit=limit)
