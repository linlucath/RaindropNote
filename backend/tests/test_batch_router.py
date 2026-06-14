import json
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.enmus.task_status_enums import TaskStatus
from app.routers import batch


def _build_youtube_channel_page_html(*, videos: list[dict], continuation_token: str | None = None) -> str:
    rich_contents = []
    for video in videos:
        rich_contents.append({
            "richItemRenderer": {
                "content": {
                    "lockupViewModel": {
                        "contentId": video["video_id"],
                        "contentType": "LOCKUP_CONTENT_TYPE_VIDEO",
                        "metadata": {
                            "lockupMetadataViewModel": {
                                "title": {"content": video["title"]},
                                "metadata": {
                                    "contentMetadataViewModel": {
                                        "metadataRows": [{
                                            "metadataParts": [
                                                {"text": {"content": video["view_text"]}},
                                                {"text": {"content": video.get("published_text") or "1天前"}},
                                            ]
                                        }]
                                    }
                                }
                            }
                        },
                        "rendererContext": {
                            "commandContext": {
                                "onTap": {
                                    "innertubeCommand": {
                                        "watchEndpoint": {"videoId": video["video_id"]}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        })

    if continuation_token:
        rich_contents.append({
            "continuationItemRenderer": {
                "continuationEndpoint": {
                    "continuationCommand": {"token": continuation_token}
                }
            }
        })

    payload = {
        "contents": {
            "twoColumnBrowseResultsRenderer": {
                "tabs": [
                    {},
                    {
                        "tabRenderer": {
                            "content": {
                                "richGridRenderer": {
                                    "header": {
                                        "chipBarViewModel": {
                                            "chips": [
                                                {"chipViewModel": {"text": "最新", "selected": True}},
                                                {"chipViewModel": {"text": "最热门", "selected": False}},
                                                {"chipViewModel": {"text": "最早", "selected": False}},
                                            ]
                                        }
                                    },
                                    "contents": rich_contents,
                                }
                            }
                        }
                    },
                ]
            }
        }
    }
    config = {
        "INNERTUBE_API_KEY": "test-api-key",
        "INNERTUBE_CLIENT_VERSION": "2.20260529.01.00",
        "VISITOR_DATA": "visitor-data",
        "INNERTUBE_CONTEXT": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20260529.01.00",
                "hl": "zh-CN",
                "gl": "JP",
                "visitorData": "visitor-data",
                "originalUrl": "https://www.youtube.com/@NewelOfKnowledge/videos?view=0&sort=p&flow=grid",
            },
            "request": {"useSsl": True},
        },
    }
    return (
        "<html><head>"
        f"<script>ytcfg.set({json.dumps(config, ensure_ascii=False)});</script>"
        f"<script>var ytInitialData = {json.dumps(payload, ensure_ascii=False)};</script>"
        "</head><body></body></html>"
    )


class TestBatchRouter(unittest.TestCase):
    def test_old_private_batch_preview_helpers_remain_importable_on_router(self):
        helper_names = [
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
            "_request_youtube_browse_continuation",
            "_preview_youtube_popular_channel_page",
            "_page_fetch_window",
            "_preview_youtube_fallback_page",
            "_preview_bilibili_flat_page",
        ]

        missing_helpers = [name for name in helper_names if not callable(getattr(batch, name, None))]

        self.assertEqual(missing_helpers, [])

    def test_task_status_description_includes_cancelling_and_cancelled(self):
        self.assertEqual(TaskStatus.description(TaskStatus.CANCELLING), "正在停止")
        self.assertEqual(TaskStatus.description(TaskStatus.CANCELLED), "已取消")

    def test_task_status_description_matches_progress_page_copy(self):
        self.assertEqual(TaskStatus.description(TaskStatus.TRANSCRIBING), "转写中")
        self.assertEqual(TaskStatus.description(TaskStatus.SUCCESS), "已完成")

    def test_normalizes_flat_playlist_entries(self):
        videos = batch.normalize_bilibili_entries([
            {"id": "BV123", "url": "https://www.bilibili.com/video/BV123"},
            {"id": "BV456"},
            {"id": None, "url": "https://example.com"},
        ])

        self.assertEqual(videos, [
            {
                "video_id": "BV123",
                "video_url": "https://www.bilibili.com/video/BV123",
                "title": "",
                "platform": "bilibili",
            },
            {
                "video_id": "BV456",
                "video_url": "https://www.bilibili.com/video/BV456",
                "title": "",
                "platform": "bilibili",
            },
        ])

    def test_normalizes_youtube_entries_and_sorts_by_view_count_desc(self):
        videos = batch.normalize_youtube_entries([
            {
                "id": "yt-1",
                "url": "https://www.youtube.com/watch?v=yt-1",
                "title": "Video 1",
                "channel": "Channel A",
                "view_count": 1200,
            },
            {
                "id": "yt-2",
                "url": "https://www.youtube.com/watch?v=yt-2",
                "title": "Video 2",
                "channel": "Channel A",
                "view_count": 9800,
            },
            {
                "id": "yt-3",
                "url": "https://www.youtube.com/watch?v=yt-3",
                "title": "Video 3",
                "channel": "Channel A",
                "view_count": 3600,
            },
        ])

        self.assertEqual([item["video_id"] for item in videos], ["yt-2", "yt-3", "yt-1"])
        self.assertEqual(videos[0]["author_name"], "Channel A")
        self.assertEqual(videos[0]["view_count"], 9800)

    def test_preview_limits_videos(self):
        with patch("app.routers.batch._extract_flat_playlist", return_value={
            "entries": [
                {"id": "BV1"},
                {"id": "BV2"},
                {"id": "BV3"},
            ]
        }):
            videos = batch.preview_bilibili_space("https://example.com/videos", limit=2)

        self.assertEqual([v["video_id"] for v in videos], ["BV1", "BV2"])

    def test_preview_enriches_missing_titles_from_video_metadata(self):
        with patch("app.routers.batch._extract_flat_playlist", return_value={
            "entries": [
                {"id": "BV1", "url": "https://www.bilibili.com/video/BV1"},
                {"id": "BV2", "title": "已有标题"},
            ]
        }), patch("app.routers.batch._extract_video_metadata", return_value={"title": "补全标题"}) as extract_video:
            videos = batch.preview_bilibili_space("https://example.com/videos", limit=2)

        self.assertEqual(videos[0]["title"], "补全标题")
        self.assertEqual(videos[1]["title"], "已有标题")
        extract_video.assert_called_once_with("https://www.bilibili.com/video/BV1")

    def test_enrich_missing_titles_retries_failed_metadata_lookup(self):
        videos = [
            {"video_id": "BV1", "video_url": "https://www.bilibili.com/video/BV1", "title": ""},
        ]

        with patch(
            "app.routers.batch._extract_video_metadata",
            side_effect=[TimeoutError("timeout"), {"title": "补回标题"}],
        ) as extract_video:
            enriched = batch._enrich_missing_titles(videos)

        self.assertEqual(enriched[0]["title"], "补回标题")
        self.assertEqual(extract_video.call_count, 2)

    def test_preview_page_returns_has_more_when_next_page_exists(self):
        with patch("app.routers.batch._extract_flat_playlist", return_value={
            "entries": [
                {"id": "BV1", "title": "视频1"},
                {"id": "BV2", "title": "视频2"},
                {"id": "BV3", "title": "视频3"},
            ]
        }) as extract_playlist:
            payload = batch.preview_bilibili_space_page(
                "https://example.com/videos",
                page=1,
                page_size=2,
                limit=0,
            )

        self.assertEqual([v["video_id"] for v in payload["items"]], ["BV1", "BV2"])
        self.assertTrue(payload["has_more"])
        extract_playlist.assert_called_once_with(
            "https://example.com/videos",
            start=1,
            end=3,
        )

    def test_preview_page_marks_processed_videos_with_existing_task_id(self):
        with patch("app.routers.batch._extract_flat_playlist", return_value={
            "entries": [
                {"id": "BV1", "title": "已处理视频"},
                {"id": "BV2", "title": "未处理视频"},
            ]
        }), patch("app.routers.batch.find_existing_task_id", side_effect=lambda video_id, mode=None: {
            "BV1": "existing-task-1",
        }.get(video_id)):
            payload = batch.preview_bilibili_space_page(
                "https://example.com/videos",
                page=1,
                page_size=2,
                limit=0,
            )

        self.assertEqual(payload["items"][0]["processed_task_id"], "existing-task-1")
        self.assertNotIn("processed_task_id", payload["items"][1])

    def test_preview_page_respects_limit_and_stops_loading_more(self):
        with patch("app.routers.batch._extract_flat_playlist", return_value={
            "entries": [
                {"id": "BV41", "title": "视频41"},
                {"id": "BV42", "title": "视频42"},
                {"id": "BV43", "title": "视频43"},
            ]
        }) as extract_playlist:
            payload = batch.preview_bilibili_space_page(
                "https://example.com/videos",
                page=3,
                page_size=20,
                limit=42,
            )

        self.assertEqual([v["video_id"] for v in payload["items"]], ["BV41", "BV42"])
        self.assertFalse(payload["has_more"])
        extract_playlist.assert_called_once_with(
            "https://example.com/videos",
            start=41,
            end=42,
        )

    def test_preview_page_uses_uploader_api_for_bilibili_space_urls(self):
        uploader_service = Mock()
        uploader_service.get_uploader_videos_page.return_value = {
            "items": [
                {
                    "video_id": "BV1",
                    "video_url": "https://www.bilibili.com/video/BV1",
                    "title": "视频1",
                }
            ],
            "page": 1,
            "page_size": 2,
            "has_more": True,
            "total": None,
        }

        with patch.object(batch, "_uploader_video_service", uploader_service, create=True), \
                patch("app.routers.batch._extract_flat_playlist") as extract_playlist:
            batch.preview_bilibili_space_page(
                "https://space.bilibili.com/1/upload/video",
                page=1,
                page_size=2,
                limit=42,
            )

        uploader_service.get_uploader_videos_page.assert_called_once_with(
            mid="1",
            page=1,
            page_size=2,
            limit=42,
            order="click",
        )
        extract_playlist.assert_not_called()

    def test_preview_page_uses_uploader_api_for_bilibili_space_homepage_urls(self):
        uploader_service = Mock()
        uploader_service.get_uploader_videos_page.return_value = {
            "items": [
                {
                    "video_id": "BV1",
                    "video_url": "https://www.bilibili.com/video/BV1",
                    "title": "视频1",
                }
            ],
            "page": 1,
            "page_size": 2,
            "has_more": False,
            "total": None,
        }

        with patch.object(batch, "_uploader_video_service", uploader_service, create=True), \
                patch("app.routers.batch._extract_flat_playlist") as extract_playlist:
            batch.preview_bilibili_space_page(
                "https://space.bilibili.com/280780745?",
                page=1,
                page_size=2,
                limit=42,
            )

        uploader_service.get_uploader_videos_page.assert_called_once_with(
            mid="280780745",
            page=1,
            page_size=2,
            limit=42,
            order="click",
        )
        extract_playlist.assert_not_called()

    def test_batch_preview_uses_popular_chip_continuation_for_first_youtube_page(self):
        response = Mock()
        response.text = (
            "<html><head>"
            "<script>ytcfg.set("
            + json.dumps({
                "INNERTUBE_API_KEY": "test-api-key",
                "INNERTUBE_CLIENT_VERSION": "2.20260529.01.00",
                "VISITOR_DATA": "visitor-data",
                "INNERTUBE_CONTEXT": {
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": "2.20260529.01.00",
                        "hl": "zh-CN",
                        "gl": "JP",
                        "visitorData": "visitor-data",
                        "originalUrl": "https://www.youtube.com/@NewelOfKnowledge/videos?view=0&sort=p&flow=grid",
                    },
                    "request": {"useSsl": True},
                },
            }, ensure_ascii=False)
            + ");</script>"
            "<script>var ytInitialData = "
            + json.dumps({
                "contents": {
                    "twoColumnBrowseResultsRenderer": {
                        "tabs": [
                            {},
                            {
                                "tabRenderer": {
                                    "content": {
                                        "richGridRenderer": {
                                            "header": {
                                                "chipBarViewModel": {
                                                    "chips": [
                                                        {"chipViewModel": {"text": "最新", "selected": True}},
                                                        {
                                                            "chipViewModel": {
                                                                "text": "最热门",
                                                                "selected": False,
                                                                "tapCommand": {
                                                                    "innertubeCommand": {
                                                                        "continuationCommand": {
                                                                            "token": "popular-chip-token"
                                                                        }
                                                                    }
                                                                },
                                                            }
                                                        },
                                                    ]
                                                }
                                            },
                                            "contents": [
                                                {
                                                    "richItemRenderer": {
                                                        "content": {
                                                            "lockupViewModel": {
                                                                "contentId": "recent-1",
                                                                "contentType": "LOCKUP_CONTENT_TYPE_VIDEO",
                                                                "metadata": {
                                                                    "lockupMetadataViewModel": {
                                                                        "title": {"content": "最近发布视频"},
                                                                        "metadata": {
                                                                            "contentMetadataViewModel": {
                                                                                "metadataRows": [{
                                                                                    "metadataParts": [
                                                                                        {"text": {"content": "100次观看"}},
                                                                                        {"text": {"content": "1天前"}},
                                                                                    ]
                                                                                }]
                                                                            }
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    }
                                }
                            },
                        ]
                    }
                }
            }, ensure_ascii=False)
            + ";</script></head><body></body></html>"
        )
        response.raise_for_status.return_value = None

        continuation_response = Mock()
        continuation_response.raise_for_status.return_value = None
        continuation_response.json.return_value = {
            "onResponseReceivedActions": [{
                "appendContinuationItemsAction": {
                    "continuationItems": [
                        {
                            "richItemRenderer": {
                                "content": {
                                    "lockupViewModel": {
                                        "contentId": "popular-1",
                                        "contentType": "LOCKUP_CONTENT_TYPE_VIDEO",
                                        "metadata": {
                                            "lockupMetadataViewModel": {
                                                "title": {"content": "热门视频 1"},
                                                "metadata": {
                                                    "contentMetadataViewModel": {
                                                        "metadataRows": [{
                                                            "metadataParts": [
                                                                {"text": {"content": "88万次观看"}},
                                                                {"text": {"content": "1年前"}},
                                                            ]
                                                        }]
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "richItemRenderer": {
                                "content": {
                                    "lockupViewModel": {
                                        "contentId": "popular-2",
                                        "contentType": "LOCKUP_CONTENT_TYPE_VIDEO",
                                        "metadata": {
                                            "lockupMetadataViewModel": {
                                                "title": {"content": "热门视频 2"},
                                                "metadata": {
                                                    "contentMetadataViewModel": {
                                                        "metadataRows": [{
                                                            "metadataParts": [
                                                                {"text": {"content": "42万次观看"}},
                                                                {"text": {"content": "2年前"}},
                                                            ]
                                                        }]
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        },
                    ]
                }
            }]
        }

        with patch("app.routers.batch.requests.get", return_value=response), \
                patch("app.routers.batch.requests.post", return_value=continuation_response) as requests_post:
            payload = batch.preview_bilibili_space_page(
                "https://www.youtube.com/@NewelOfKnowledge",
                page=1,
                page_size=2,
                limit=0,
            )

        self.assertEqual([item["video_id"] for item in payload["items"]], ["popular-1", "popular-2"])
        self.assertEqual(payload["items"][0]["view_count"], 880000)
        self.assertEqual(
            requests_post.call_args.kwargs["json"]["continuation"],
            "popular-chip-token",
        )

    def test_batch_preview_uses_popular_continuation_across_pages_instead_of_sorting_current_page_only(self):
        response = Mock()
        response.text = (
            "<html><head>"
            "<script>ytcfg.set("
            + json.dumps({
                "INNERTUBE_API_KEY": "test-api-key",
                "INNERTUBE_CLIENT_VERSION": "2.20260529.01.00",
                "VISITOR_DATA": "visitor-data",
                "INNERTUBE_CONTEXT": {
                    "client": {
                        "clientName": "WEB",
                        "clientVersion": "2.20260529.01.00",
                        "hl": "zh-CN",
                        "gl": "JP",
                        "visitorData": "visitor-data",
                    },
                    "request": {"useSsl": True},
                },
            }, ensure_ascii=False)
            + ");</script>"
            "<script>var ytInitialData = "
            + json.dumps({
                "contents": {
                    "twoColumnBrowseResultsRenderer": {
                        "tabs": [
                            {},
                            {
                                "tabRenderer": {
                                    "content": {
                                        "richGridRenderer": {
                                            "header": {
                                                "chipBarViewModel": {
                                                    "chips": [
                                                        {"chipViewModel": {"text": "最新", "selected": True}},
                                                        {
                                                            "chipViewModel": {
                                                                "text": "最热门",
                                                                "selected": False,
                                                                "tapCommand": {
                                                                    "innertubeCommand": {
                                                                        "continuationCommand": {
                                                                            "token": "popular-chip-token"
                                                                        }
                                                                    }
                                                                },
                                                            }
                                                        },
                                                    ]
                                                }
                                            },
                                            "contents": [],
                                        }
                                    }
                                }
                            },
                        ]
                    }
                }
            }, ensure_ascii=False)
            + ";</script></head><body></body></html>"
        )
        response.raise_for_status.return_value = None

        popular_page_response = Mock()
        popular_page_response.raise_for_status.return_value = None
        popular_page_response.json.return_value = {
            "onResponseReceivedActions": [
                {"reloadContinuationItemsCommand": {"continuationItems": []}},
                {
                    "reloadContinuationItemsCommand": {
                        "continuationItems": [
                            *[
                                {
                                    "richItemRenderer": {
                                        "content": {
                                            "lockupViewModel": {
                                                "contentId": f"popular-{index}",
                                                "contentType": "LOCKUP_CONTENT_TYPE_VIDEO",
                                                "metadata": {
                                                    "lockupMetadataViewModel": {
                                                        "title": {"content": f"热门视频 {index}"},
                                                        "metadata": {
                                                            "contentMetadataViewModel": {
                                                                "metadataRows": [{
                                                                    "metadataParts": [
                                                                        {"text": {"content": f"{100 - index}万次观看"}},
                                                                        {"text": {"content": "1年前"}},
                                                                    ]
                                                                }]
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                                for index in range(1, 31)
                            ],
                            {
                                "continuationItemRenderer": {
                                    "continuationEndpoint": {
                                        "continuationCommand": {"token": "next-popular-page-token"}
                                    }
                                }
                            },
                        ]
                    }
                },
            ]
        }

        continuation_response = Mock()
        continuation_response.raise_for_status.return_value = None
        continuation_response.json.return_value = {
            "onResponseReceivedActions": [{
                "reloadContinuationItemsCommand": {
                    "continuationItems": [
                        {
                            "richItemRenderer": {
                                "content": {
                                    "lockupViewModel": {
                                        "contentId": f"popular-{index}",
                                        "contentType": "LOCKUP_CONTENT_TYPE_VIDEO",
                                        "metadata": {
                                            "lockupMetadataViewModel": {
                                                "title": {"content": f"热门视频 {index}"},
                                                "metadata": {
                                                    "contentMetadataViewModel": {
                                                        "metadataRows": [{
                                                            "metadataParts": [
                                                                {"text": {"content": f"{100 - index}万次观看"}},
                                                                {"text": {"content": "2年前"}},
                                                            ]
                                                        }]
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        for index in range(31, 61)
                    ]
                }
            }]
        }

        with patch("app.routers.batch.requests.get", return_value=response), \
                patch(
                    "app.routers.batch.requests.post",
                    side_effect=[popular_page_response, continuation_response],
                ) as requests_post:
            payload = batch.preview_bilibili_space_page(
                "https://www.youtube.com/@NewelOfKnowledge",
                page=2,
                page_size=20,
                limit=0,
            )

        self.assertEqual(
            [item["video_id"] for item in payload["items"]],
            [f"popular-{index}" for index in range(21, 41)],
        )
        self.assertEqual(
            [call.kwargs["json"]["continuation"] for call in requests_post.call_args_list],
            ["popular-chip-token", "next-popular-page-token"],
        )

    def test_batch_preview_supports_youtube_handle_urls(self):
        response = Mock()
        response.text = _build_youtube_channel_page_html(
            videos=[
                {
                    "video_id": "yt-1",
                    "title": "第一条 YouTube 视频",
                    "view_text": "12万次观看",
                },
                {
                    "video_id": "yt-2",
                    "title": "第二条 YouTube 视频",
                    "view_text": "8.9万次观看",
                },
            ],
            continuation_token="next-page-token",
        )
        response.raise_for_status.return_value = None

        with patch("app.routers.batch.requests.get", return_value=response) as requests_get, \
                patch("app.routers.batch._extract_flat_playlist") as extract_playlist:
            payload = batch.preview_bilibili_space_page(
                "https://www.youtube.com/@NewelOfKnowledge",
                page=1,
                page_size=2,
                limit=0,
            )

        self.assertEqual(
            payload["items"],
            [
                {
                    "video_id": "yt-1",
                    "video_url": "https://www.youtube.com/watch?v=yt-1",
                    "title": "第一条 YouTube 视频",
                    "author_name": "",
                    "view_count": 120000,
                    "platform": "youtube",
                },
                {
                    "video_id": "yt-2",
                    "video_url": "https://www.youtube.com/watch?v=yt-2",
                    "title": "第二条 YouTube 视频",
                    "author_name": "",
                    "view_count": 89000,
                    "platform": "youtube",
                },
            ],
        )
        self.assertTrue(payload["has_more"])
        requests_get.assert_called_once()
        self.assertIn(
            "https://www.youtube.com/@NewelOfKnowledge/videos?view=0&sort=p&flow=grid",
            requests_get.call_args.args,
        )
        extract_playlist.assert_not_called()

    def test_batch_preview_falls_back_to_recent_youtube_entries_when_popular_page_request_fails(self):
        with patch("app.routers.batch.requests.get", side_effect=RuntimeError("boom")), \
                patch("app.routers.batch._extract_flat_playlist", return_value={
                    "entries": [
                        {
                            "id": "yt-1",
                            "url": "https://www.youtube.com/watch?v=yt-1",
                            "title": "第一条 YouTube 视频",
                            "channel": "Channel A",
                            "view_count": 1234,
                        },
                        {
                            "id": "yt-2",
                            "url": "https://www.youtube.com/watch?v=yt-2",
                            "title": "第二条 YouTube 视频",
                            "channel": "Channel A",
                            "view_count": 1200,
                        },
                    ]
                }) as extract_playlist:
            payload = batch.preview_bilibili_space_page(
                "https://www.youtube.com/@NewelOfKnowledge",
                page=1,
                page_size=2,
                limit=0,
            )

        self.assertEqual([item["video_id"] for item in payload["items"]], ["yt-1", "yt-2"])
        extract_playlist.assert_called_once_with(
            "https://www.youtube.com/@NewelOfKnowledge/videos",
            start=1,
            end=3,
        )

    def test_batch_preview_falls_back_to_youtube_uploads_playlist_when_channel_tab_is_empty(self):
        responses = [
            {
                "channel_id": "UC5fy9izAhlANCISUdU8quDg",
                "entries": [],
            },
            {
                "entries": [
                    {
                        "id": "yt-1",
                        "url": "https://www.youtube.com/watch?v=yt-1",
                        "title": "第一条 YouTube 视频",
                    },
                    {
                        "id": "yt-2",
                        "url": "https://www.youtube.com/watch?v=yt-2",
                        "title": "第二条 YouTube 视频",
                    },
                    {
                        "id": "yt-3",
                        "url": "https://www.youtube.com/watch?v=yt-3",
                        "title": "第三条 YouTube 视频",
                    },
                ]
            },
        ]

        with patch("app.routers.batch.requests.get", side_effect=RuntimeError("popular page failed")), \
                patch("app.routers.batch._extract_flat_playlist", side_effect=responses) as extract_playlist:
            payload = batch.preview_bilibili_space_page(
                "https://www.youtube.com/@NewelOfKnowledge",
                page=1,
                page_size=2,
                limit=0,
            )

        self.assertEqual([item["video_id"] for item in payload["items"]], ["yt-1", "yt-2"])
        self.assertTrue(payload["has_more"])
        self.assertEqual(extract_playlist.call_count, 2)
        first_call = extract_playlist.call_args_list[0]
        second_call = extract_playlist.call_args_list[1]
        self.assertEqual(first_call.args[0], "https://www.youtube.com/@NewelOfKnowledge/videos")
        self.assertEqual(second_call.args[0], "https://www.youtube.com/playlist?list=UU5fy9izAhlANCISUdU8quDg")

    def test_preview_page_preserves_explicit_bilibili_space_order_in_uploader_api(self):
        uploader_service = Mock()
        uploader_service.get_uploader_videos_page.return_value = {
            "items": [],
            "page": 1,
            "page_size": 2,
            "has_more": False,
            "total": None,
        }

        with patch.object(batch, "_uploader_video_service", uploader_service, create=True), \
                patch("app.routers.batch._extract_flat_playlist") as extract_playlist:
            batch.preview_bilibili_space_page(
                "https://space.bilibili.com/1/upload/video?order=pubdate",
                page=1,
                page_size=2,
                limit=0,
            )

        uploader_service.get_uploader_videos_page.assert_called_once_with(
            mid="1",
            page=1,
            page_size=2,
            limit=0,
            order="pubdate",
        )
        extract_playlist.assert_not_called()

    def test_extract_flat_playlist_omits_playlistend_when_limit_is_zero(self):
        captured_options = {}

        class FakeYoutubeDL:
            def __init__(self, opts):
                captured_options.update(opts)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, space_url, download=False):
                return {"entries": []}

        with patch("app.routers.batch.yt_dlp.YoutubeDL", FakeYoutubeDL):
            batch._extract_flat_playlist("https://space.bilibili.com/1/upload/video", limit=0)

        self.assertNotIn("playlistend", captured_options)

    def test_apply_bilibili_cookie_uses_router_cookie_file_path_patch(self):
        with patch("app.routers.batch._cookie_manager.get", return_value=""), \
                patch("app.routers.batch._cookie_file_path", return_value=Path("/tmp/router-cookies.txt")), \
                patch("pathlib.Path.exists", return_value=True):
            options = batch._apply_bilibili_cookie({"http_headers": {}})

        self.assertEqual(options["cookiefile"], "/tmp/router-cookies.txt")

    def test_apply_bilibili_cookie_prefers_env_cookie_over_cookiefile(self):
        with patch("app.routers.batch._cookie_file_path", return_value=Path("/tmp/existing-cookies.txt")), \
                patch("pathlib.Path.exists", return_value=True), \
                patch.dict("os.environ", {"BILIBILI_COOKIE": "SESSDATA=test-cookie"}, clear=False):
            options = batch._apply_bilibili_cookie({
                "http_headers": {"User-Agent": "test-agent"},
            })

        self.assertNotIn("cookiefile", options)
        self.assertEqual(options["http_headers"]["Cookie"], "SESSDATA=test-cookie")

    def test_youtube_popular_preview_uses_router_parser_patch(self):
        class FakeResponse:
            text = _build_youtube_channel_page_html(
                videos=[{"video_id": "yt-runtime1", "title": "Runtime 1", "view_text": "1,000 views"}],
                continuation_token=None,
            )

            def raise_for_status(self):
                return None

        with patch("app.routers.batch.requests.get", return_value=FakeResponse()), patch(
            "app.routers.batch._extract_youtube_page_initial_data",
            side_effect=ValueError("router parser patch"),
        ):
            with self.assertRaisesRegex(ValueError, "router parser patch"):
                batch._preview_youtube_popular_channel_page(
                    "https://www.youtube.com/@demo/videos",
                    page=1,
                    page_size=1,
                    limit=1,
                )

    def test_preview_patchables_do_not_leak_into_service_module_after_router_call(self):
        from app.services import batch_preview as batch_preview_service

        original_extract_flat_playlist = batch_preview_service._extract_flat_playlist
        self.addCleanup(
            setattr,
            batch_preview_service,
            "_extract_flat_playlist",
            original_extract_flat_playlist,
        )

        with patch("app.routers.batch._extract_flat_playlist", return_value={
            "entries": [{"id": "BV1", "title": "视频1"}],
        }):
            videos = batch.preview_bilibili_space("https://example.com/videos", limit=1)

        self.assertEqual([video["video_id"] for video in videos], ["BV1"])
        self.assertIs(batch_preview_service._extract_flat_playlist, original_extract_flat_playlist)

    def test_preview_normalizer_router_patch_is_forwarded_to_service_call(self):
        normalized_video = {
            "video_id": "patched-video",
            "video_url": "https://example.com/patched-video",
            "title": "Patched title",
            "platform": "bilibili",
        }

        with patch("app.routers.batch._extract_flat_playlist", return_value={
            "entries": [{"id": "not-a-bv"}],
        }), patch(
            "app.routers.batch.normalize_bilibili_entries",
            return_value=[normalized_video],
        ):
            videos = batch.preview_bilibili_space("https://example.com/videos", limit=1)

        self.assertEqual(videos, [normalized_video])

    def test_batch_state_patchables_do_not_leak_into_service_module_after_router_call(self):
        from app.services import batch_state as batch_state_service

        original_output_dir = batch_state_service.BATCH_OUTPUT_DIR
        original_batches = batch_state_service._batches
        original_lock = batch_state_service._batch_lock
        self.addCleanup(setattr, batch_state_service, "BATCH_OUTPUT_DIR", original_output_dir)
        self.addCleanup(setattr, batch_state_service, "_batches", original_batches)
        self.addCleanup(setattr, batch_state_service, "_batch_lock", original_lock)

        with tempfile.TemporaryDirectory() as tmp:
            patched_output_dir = Path(tmp) / "batches"
            with patch("app.routers.batch.BATCH_OUTPUT_DIR", patched_output_dir):
                batch._save_batch({"batch_id": "batch-leak-check"})

            self.assertTrue((patched_output_dir / "batch-leak-check.json").exists())

        self.assertEqual(batch_state_service.BATCH_OUTPUT_DIR, original_output_dir)
        self.assertIs(batch_state_service._batches, original_batches)
        self.assertIs(batch_state_service._batch_lock, original_lock)

    def test_batch_state_router_wrapper_passes_patchables_without_mutating_service_globals(self):
        from app.services import batch_state as batch_state_service

        original_update_batch = batch_state_service.update_batch
        original_output_dir = batch_state_service.BATCH_OUTPUT_DIR
        batch_id = "batch-explicit-deps"

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict("app.routers.batch._batches", {
                    batch_id: {
                        "batch_id": batch_id,
                        "status": "PENDING",
                        "total": 1,
                        "completed": 0,
                        "items": [{"status": "PENDING"}],
                    },
                }, clear=True), \
                patch("app.routers.batch.BATCH_OUTPUT_DIR", Path(tmp) / "batches"):

            def update_batch_without_global_mutation(*args, **kwargs):
                self.assertEqual(batch_state_service.BATCH_OUTPUT_DIR, original_output_dir)
                self.assertEqual(kwargs["output_dir"], Path(tmp) / "batches")
                return original_update_batch(*args, **kwargs)

            with patch(
                "app.services.batch_state.update_batch",
                side_effect=update_batch_without_global_mutation,
            ):
                updated = batch._update_batch(batch_id, status="RUNNING")

        self.assertEqual(updated["status"], "RUNNING")

    def test_create_batch_payload_uses_router_platform_inference_patch(self):
        request = batch.BatchStartRequest(videos=[
            batch.BatchVideo(
                video_id="custom-1",
                video_url="https://example.com/watch/custom-1",
                title="自定义平台视频",
            )
        ])

        with patch("app.routers.batch._infer_platform_from_url", return_value="custom-platform"):
            payload = batch.create_batch_payload(batch_id="batch-custom", request=request)

        self.assertEqual(payload["items"][0]["platform"], "custom-platform")

    def test_find_existing_task_by_video_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "task-1.json"
            result.write_text(
                json.dumps({
                    "markdown": "# 标题\n\n内容",
                    "mode": "polished_transcript",
                    "audio_meta": {"video_id": "BV123"},
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch("app.routers.batch.NOTE_OUTPUT_DIR", Path(tmp)):
                self.assertEqual(batch.find_existing_task_id("BV123"), "task-1")
                self.assertIsNone(batch.find_existing_task_id("BV999"))

    def test_find_existing_task_matches_requested_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw_transcript = Path(tmp) / "raw-transcript.json"
            raw_transcript.write_text(
                json.dumps({
                    "markdown": "# 标题\n\n## 简体中文文字稿\n\n原始文字",
                    "audio_meta": {"video_id": "BV123"},
                }, ensure_ascii=False),
                encoding="utf-8",
            )
            polished_transcript = Path(tmp) / "polished-transcript.json"
            polished_transcript.write_text(
                json.dumps({
                    "markdown": "# 标题\n\n校对文字",
                    "mode": "polished_transcript",
                    "audio_meta": {"video_id": "BV123"},
                }, ensure_ascii=False),
                encoding="utf-8",
            )

            with patch("app.routers.batch.NOTE_OUTPUT_DIR", Path(tmp)):
                self.assertEqual(batch.find_existing_task_id("BV123", "polished_transcript"), "polished-transcript")
                self.assertEqual(batch.find_existing_task_id("BV123"), "polished-transcript")
                self.assertFalse(raw_transcript.exists())

    def test_batch_start_request_defaults_match_single_task_defaults(self):
        request = batch.BatchStartRequest(videos=[
            batch.BatchVideo(
                video_id="BV123",
                video_url="https://www.bilibili.com/video/BV123",
                title="示例视频",
            )
        ])

        self.assertFalse(request.link)
        self.assertFalse(request.screenshot)
        self.assertEqual(request.format, [])
        self.assertIsNone(request.style)
        self.assertIsNone(request.extras)
        self.assertEqual(request.mode, "polished_transcript")
        self.assertFalse(request.video_understanding)
        self.assertEqual(request.video_interval, 0)
        self.assertEqual(request.grid_size, [])

    def test_new_batch_payload_contains_progress_metadata(self):
        @asynccontextmanager
        async def lifespan(_app):
            yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(batch.router, prefix="/api")

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict("app.routers.batch._batches", clear=True), \
                patch("app.routers.batch.BATCH_OUTPUT_DIR", Path(tmp)), \
                patch("app.routers.batch.uuid.uuid4", return_value="batch-123"), \
                patch("app.routers.batch.run_batch"):
            client = TestClient(app)
            response = client.post("/api/batch/start", json={
                "videos": [
                    {
                        "video_id": "BV123",
                        "video_url": "https://www.bilibili.com/video/BV123",
                        "title": "示例视频",
                    }
                ],
            })

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["batch_id"], "batch-123")

            batch_file = Path(tmp) / "batch-123.json"
            self.assertTrue(batch_file.exists())
            payload = json.loads(batch_file.read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "PENDING")
        self.assertEqual(payload["title"], "批量文字稿任务")
        self.assertEqual(payload["source_label"], "Bilibili")
        self.assertFalse(payload["cancel_requested"])
        self.assertIsNone(payload["current_item_title"])
        self.assertIsNone(payload["current_item_index"])
        self.assertIsInstance(payload["created_at"], str)
        self.assertEqual(payload["created_at"], payload["updated_at"])

    def test_run_batch_passes_single_task_options_through(self):
        request = batch.BatchStartRequest(
            videos=[
                batch.BatchVideo(
                    video_id="BV123",
                    video_url="https://www.bilibili.com/video/BV123",
                    title="示例视频",
                )
            ],
            mode="polished_transcript",
            quality=batch.DownloadQuality.fast,
            skip_existing=False,
            concurrency=1,
            link=True,
            screenshot=True,
            model_name="deepseek-chat",
            provider_id="provider-1",
            format=["toc", "summary"],
            style="minimal",
            extras="保留关键时间点",
            video_understanding=True,
            video_interval=8,
            grid_size=[3, 2],
        )
        batch_id = "batch-1"

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict("app.routers.batch._batches", {
                    batch_id: {
                        "batch_id": batch_id,
                        "status": "PENDING",
                        "total": 1,
                        "completed": 0,
                        "items": [{
                            "video_id": "BV123",
                            "video_url": "https://www.bilibili.com/video/BV123",
                            "title": "示例视频",
                            "status": "PENDING",
                            "task_id": None,
                            "message": "",
                        }],
                    }
                }, clear=True), \
                patch("app.routers.batch.BATCH_OUTPUT_DIR", Path(tmp)), \
                patch("app.routers.batch.NOTE_OUTPUT_DIR", Path(tmp)), \
                patch("app.routers.batch.uuid.uuid4", return_value="task-123"), \
                patch("app.routers.batch.run_note_task") as run_note_task:
            run_note_task.side_effect = lambda **kwargs: (Path(tmp) / f"{kwargs['task_id']}.json").write_text(
                json.dumps({"ok": True}),
                encoding="utf-8",
            )

            batch.run_batch(batch_id, request)

        run_note_task.assert_called_once_with(
            task_id="task-123",
            video_url="https://www.bilibili.com/video/BV123",
            platform="bilibili",
            quality=batch.DownloadQuality.fast,
            link=True,
            screenshot=True,
            model_name="deepseek-chat",
            provider_id="provider-1",
            _format=["toc", "summary"],
            style="minimal",
            extras="保留关键时间点",
            video_understanding=True,
            video_interval=8,
            grid_size=[3, 2],
            mode="polished_transcript",
        )

    def test_batch_start_uses_video_platform_when_present(self):
        request = batch.BatchStartRequest(
            videos=[
                batch.BatchVideo(
                    video_id="yt-123",
                    video_url="https://www.youtube.com/watch?v=yt-123",
                    title="示例 YouTube 视频",
                    platform="youtube",
                )
            ],
            skip_existing=False,
        )
        batch_id = "batch-youtube"

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict("app.routers.batch._batches", {
                    batch_id: {
                        "batch_id": batch_id,
                        "status": "PENDING",
                        "total": 1,
                        "completed": 0,
                        "items": [{
                            "video_id": "yt-123",
                            "video_url": "https://www.youtube.com/watch?v=yt-123",
                            "title": "示例 YouTube 视频",
                            "platform": "youtube",
                            "status": "PENDING",
                            "task_id": None,
                            "message": "",
                        }],
                    }
                }, clear=True), \
                patch("app.routers.batch.BATCH_OUTPUT_DIR", Path(tmp)), \
                patch("app.routers.batch.NOTE_OUTPUT_DIR", Path(tmp)), \
                patch("app.routers.batch.uuid.uuid4", return_value="task-youtube"), \
                patch("app.routers.batch.run_note_task") as run_note_task:
            run_note_task.side_effect = lambda **kwargs: (Path(tmp) / f"{kwargs['task_id']}.json").write_text(
                json.dumps({"ok": True}),
                encoding="utf-8",
            )

            batch.run_batch(batch_id, request)

        self.assertEqual(run_note_task.call_args.kwargs["platform"], "youtube")


if __name__ == "__main__":
    unittest.main()
