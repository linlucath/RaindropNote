import unittest

from app.services.batch_preview_youtube_extractors import (
    extract_youtube_lockup_video,
    extract_youtube_rich_grid_continuation_token,
    extract_youtube_videos_from_rich_grid_contents,
    parse_youtube_view_count,
)


def _lockup(
    *,
    video_id: str = "yt-1",
    title: str = "Test video",
    view_text: str = "1.2K views",
    author: str | None = None,
    content_type: str = "LOCKUP_CONTENT_TYPE_VIDEO",
) -> dict:
    metadata_rows = [
        {
            "metadataParts": [{"text": {"content": view_text}}],
        }
    ]
    if author is not None:
        metadata_rows.append({
            "metadataParts": [{"text": {"content": author}}],
        })

    return {
        "contentId": video_id,
        "contentType": content_type,
        "metadata": {
            "lockupMetadataViewModel": {
                "title": {"content": title},
                "metadata": {
                    "contentMetadataViewModel": {
                        "metadataRows": metadata_rows
                    }
                },
            }
        },
    }


def _rich_item(lockup: dict | None) -> dict:
    return {
        "richItemRenderer": {
            "content": {
                "lockupViewModel": lockup,
            }
        }
    }


class TestBatchPreviewYoutubeExtractors(unittest.TestCase):
    def test_parse_youtube_view_count_supports_suffixes_commas_and_invalid_input(self):
        cases = [
            ("1.2K views", 1200),
            ("3M views", 3000000),
            ("1,234 views", 1234),
            ("8.9万次观看", 89000),
            ("2亿次观看", 200000000),
            ("not a count", 0),
            ("", 0),
            (None, 0),
        ]

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(parse_youtube_view_count(value), expected)

    def test_extract_youtube_lockup_video_reads_core_fields(self):
        video = extract_youtube_lockup_video(
            _lockup(
                video_id="abc123",
                title="  Lockup title  ",
                view_text="12,345 views",
                author="Channel Name",
            )
        )

        self.assertEqual(
            video,
            {
                "video_id": "abc123",
                "video_url": "https://www.youtube.com/watch?v=abc123",
                "title": "Lockup title",
                "author_name": "Channel Name",
                "view_count": 12345,
                "platform": "youtube",
            },
        )

    def test_rich_grid_contents_ignore_invalid_items(self):
        videos = extract_youtube_videos_from_rich_grid_contents(
            [
                {},
                _rich_item(None),
                _rich_item(_lockup(video_id="", title="Missing id")),
                _rich_item(_lockup(video_id="short-1", content_type="LOCKUP_CONTENT_TYPE_SHORTS")),
                _rich_item(_lockup(video_id="valid-1", title="Valid 1", view_text="1K views")),
                _rich_item(_lockup(video_id="valid-1", title="Duplicate", view_text="2K views")),
                _rich_item(_lockup(video_id="valid-2", title="Valid 2", view_text="3K views")),
            ]
        )

        self.assertEqual([video["video_id"] for video in videos], ["valid-1", "valid-2"])
        self.assertEqual([video["view_count"] for video in videos], [1000, 3000])

    def test_continuation_token_missing_returns_none(self):
        self.assertIsNone(extract_youtube_rich_grid_continuation_token([{}, _rich_item(_lockup())]))


if __name__ == "__main__":
    unittest.main()
