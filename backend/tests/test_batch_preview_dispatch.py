import unittest

from app.services.batch_preview_dispatch import preview_space_page


class TestBatchPreviewDispatch(unittest.TestCase):
    def test_youtube_popular_failure_uses_fallback_page(self):
        calls: list[str] = []

        def preview_popular(*, space_url: str, page: int, page_size: int, limit: int) -> dict:
            calls.append(f"popular:{space_url}:{page}:{page_size}:{limit}")
            raise RuntimeError("popular failed")

        def preview_fallback(space_url: str, page: int, page_size: int, limit: int) -> dict:
            calls.append(f"fallback:{space_url}:{page}:{page_size}:{limit}")
            return {
                "items": [{"video_id": "yt-1"}],
                "page": page,
                "page_size": page_size,
                "has_more": False,
                "total": None,
            }

        payload = preview_space_page(
            "https://www.youtube.com/@demo",
            page=2,
            page_size=10,
            limit=30,
            infer_platform=lambda url: "youtube",
            preview_youtube_popular=preview_popular,
            preview_youtube_fallback=preview_fallback,
            parse_bilibili_space_request=lambda url: (None, "click"),
            uploader_video_service=None,
            preview_bilibili_flat=lambda space_url, page, page_size, limit: {},
        )

        self.assertEqual(payload["items"], [{"video_id": "yt-1"}])
        self.assertEqual(calls, [
            "popular:https://www.youtube.com/@demo:2:10:30",
            "fallback:https://www.youtube.com/@demo:2:10:30",
        ])


if __name__ == "__main__":
    unittest.main()
