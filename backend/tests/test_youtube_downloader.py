import unittest
from unittest.mock import patch

from app.downloaders import youtube_downloader


class TestYoutubeDownloader(unittest.TestCase):
    def test_apply_youtube_auth_prefers_configured_cookie(self):
        with patch.object(youtube_downloader.cookie_manager, "get", return_value="SID=abc123"):
            options = youtube_downloader._apply_youtube_auth({})

        self.assertNotIn("cookiesfrombrowser", options)
        self.assertEqual(options["http_headers"]["Cookie"], "SID=abc123")

    def test_apply_youtube_auth_falls_back_to_safari_browser_cookies(self):
        with patch.object(youtube_downloader.cookie_manager, "get", return_value=""):
            options = youtube_downloader._apply_youtube_auth({})

        self.assertEqual(options["cookiesfrombrowser"], ("safari",))
        self.assertNotIn("Cookie", options.get("http_headers", {}))


if __name__ == "__main__":
    unittest.main()
