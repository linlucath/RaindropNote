from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from typing import Any


BATCH_PREVIEW_PATCHABLE_NAMES = (
    "requests",
    "yt_dlp",
    "BILIBILI_COOKIES_FILE",
    "_cookie_manager",
    "_uploader_video_service",
    "infer_platform_from_url",
    "_normalize_youtube_channel_url",
    "_build_youtube_popular_videos_url",
    "_build_youtube_uploads_playlist_url",
    "_apply_default_bilibili_space_order",
    "_parse_bilibili_space_video_request",
    "_youtube_request_headers",
    "_extract_youtube_page_initial_data",
    "_parse_youtube_view_count",
    "_extract_youtube_lockup_video",
    "_extract_youtube_videos_from_rich_grid_contents",
    "_extract_youtube_rich_grid_continuation_token",
    "_extract_youtube_page_rich_grid",
    "_extract_youtube_popular_chip_token",
    "_extract_youtube_continuation_rich_grid",
    "_page_fetch_window",
    "_cookie_file_path",
    "_apply_bilibili_cookie",
    "_extract_flat_playlist",
    "_extract_video_metadata",
    "_enrich_missing_titles",
    "_request_youtube_browse_continuation",
    "_preview_youtube_popular_channel_page",
    "_preview_youtube_fallback_page",
    "_preview_bilibili_flat_page",
    "normalize_bilibili_entries",
    "normalize_youtube_entries",
)

BATCH_STATE_PATCHABLE_NAMES = (
    "BATCH_OUTPUT_DIR",
    "_batch_lock",
    "_batches",
)


def _source_value(source: Mapping[str, Any] | object, name: str) -> Any:
    if isinstance(source, Mapping):
        return source[name]
    return getattr(source, name)


def router_patch_source(
    router_globals: Mapping[str, Any],
    names: Iterable[str],
    *,
    aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    aliases = aliases or {}
    return {name: router_globals[aliases.get(name, name)] for name in names}


def sync_patchables(
    target: object,
    source: Mapping[str, Any] | object,
    names: Iterable[str],
) -> dict[str, Any]:
    previous = {name: getattr(target, name) for name in names}
    for name in names:
        setattr(target, name, _source_value(source, name))
    return previous


@contextmanager
def patched_patchables(
    target: object,
    source: Mapping[str, Any] | object,
    names: Iterable[str],
):
    previous = sync_patchables(target, source, names)
    try:
        yield previous
    finally:
        for name, value in previous.items():
            setattr(target, name, value)


def sync_router_patchables(
    target: object,
    router_globals: Mapping[str, Any],
    names: Iterable[str],
    *,
    aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return sync_patchables(
        target,
        router_patch_source(router_globals, names, aliases=aliases),
        names,
    )


@contextmanager
def patched_router_patchables(
    target: object,
    router_globals: Mapping[str, Any],
    names: Iterable[str],
    *,
    aliases: Mapping[str, str] | None = None,
):
    with patched_patchables(
        target,
        router_patch_source(router_globals, names, aliases=aliases),
        names,
    ) as previous:
        yield previous
