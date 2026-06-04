import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from app.downloaders.douyin_downloader import DouyinDownloader
from app.downloaders.douyin_parsing import (
    extract_aweme_id,
    find_urls,
    parse_audio_metadata,
)


class TestDouyinDownloader(unittest.TestCase):
    @patch("app.downloaders.douyin_downloader.cfm.get", return_value="sid_tt=test-cookie")
    def test_init_does_not_print_headers_to_stdout(self, _cookie_get):
        stdout = StringIO()

        with redirect_stdout(stdout):
            DouyinDownloader()

        self.assertEqual(stdout.getvalue(), "")

    @patch("app.downloaders.douyin_downloader.cfm.get", return_value="sid_tt=test-cookie")
    def test_init_debug_logs_do_not_include_cookie_value(self, _cookie_get):
        with patch("app.downloaders.douyin_downloader.logger") as logger:
            DouyinDownloader()

        debug_payload = " ".join(
            str(part)
            for call in logger.debug.call_args_list
            for part in [*call.args, *call.kwargs.values()]
        )
        self.assertNotIn("sid_tt=test-cookie", debug_payload)
        self.assertNotIn("Cookie", debug_payload)

    @patch("app.downloaders.douyin_downloader.cfm.get", return_value="sid_tt=test-cookie")
    @patch("app.downloaders.douyin_downloader.requests.get")
    @patch("app.downloaders.douyin_downloader.ABogus")
    @patch.object(DouyinDownloader, "gen_real_msToken", return_value="ms-token-secret")
    @patch.object(DouyinDownloader, "extract_video_id", return_value="1234567890")
    def test_fetch_video_info_debug_logs_do_not_include_signed_secrets(
        self,
        _extract_video_id,
        _gen_real_ms_token,
        abogus_cls,
        requests_get,
        _cookie_get,
    ):
        abogus_cls.return_value.get_value.return_value = "a-bogus-secret"
        response = requests_get.return_value
        response.content = b'{"ok": true}'
        response.json.return_value = {"ok": True}

        downloader = DouyinDownloader()
        with patch("app.downloaders.douyin_downloader.logger") as logger:
            downloader.fetch_video_info("https://www.douyin.com/video/1234567890")

        debug_payload = " ".join(
            str(part)
            for call in logger.debug.call_args_list
            for part in [*call.args, *call.kwargs.values()]
        )
        self.assertNotIn("sid_tt=test-cookie", debug_payload)
        self.assertNotIn("ms-token-secret", debug_payload)
        self.assertNotIn("a-bogus-secret", debug_payload)
        self.assertNotIn("Cookie", debug_payload)

    @patch("app.downloaders.douyin_downloader.cfm.get", return_value="sid_tt=test-cookie")
    @patch.object(DouyinDownloader, "extract_video_id", return_value="1234567890")
    @patch.object(DouyinDownloader, "fetch_video_info")
    def test_download_video_cached_path_does_not_print_debug_output(
        self,
        fetch_video_info,
        _extract_video_id,
        _cookie_get,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "1234567890.mp4"
            video_path.write_bytes(b"cached video")
            stdout = StringIO()

            with redirect_stdout(stdout):
                downloader = DouyinDownloader()
                result = downloader.download_video(
                    "https://www.douyin.com/video/1234567890",
                    output_dir=tmp,
                )

        self.assertEqual(result, str(video_path))
        self.assertEqual(stdout.getvalue(), "")
        fetch_video_info.assert_not_called()

    def test_find_urls_and_extract_aweme_id_preserve_legacy_patterns(self):
        shared_text = (
            "复制打开抖音 https://v.douyin.com/0pcFVdG_lx4/ "
            "也可以看 https://example.com/a?b=1"
        )

        self.assertEqual(
            find_urls(shared_text),
            ["https://v.douyin.com/0pcFVdG_lx4/", "https://example.com/a?b=1"],
        )
        self.assertEqual(
            extract_aweme_id("https://www.douyin.com/video/7345492945006595379"),
            "7345492945006595379",
        )
        self.assertEqual(
            extract_aweme_id("https://www.douyin.com/?aweme_id=7345492945006595380"),
            "7345492945006595380",
        )
        self.assertEqual(extract_aweme_id("https://www.douyin.com/user/MS4wLjAB"), "")

    @patch("app.downloaders.douyin_downloader.cfm.get", return_value="sid_tt=test-cookie")
    @patch("app.downloaders.douyin_downloader.requests.head")
    def test_extract_video_id_keeps_legacy_patch_paths(self, head, _cookie_get):
        head.return_value.url = "https://www.douyin.com/video/13579"
        downloader = DouyinDownloader()

        with patch.object(downloader, "find_url", return_value=["https://v.douyin.com/share/"]):
            result = downloader.extract_video_id("copy text with a short link")

        self.assertEqual(result, "13579")
        head.assert_called_once_with("https://v.douyin.com/share/", allow_redirects=True)

    def test_parse_audio_metadata_preserves_legacy_field_shape(self):
        video_data = {
            "aweme_detail": {
                "aweme_id": "24680",
                "caption": "#caption",
                "item_title": "demo title",
                "music": {"play_url": {"uri": "https://audio.example/demo.mp3"}},
                "video": {
                    "cover": {"uri": "cover"},
                    "cover_original_scale": {"url_list": ["https://cover.example/original.jpg"]},
                    "duration": 12345,
                },
                "video_tag": [
                    {"tag_name": "tag-a"},
                    {"tag_name": ""},
                    {"tag_name": "tag-b"},
                ],
            },
            "video": {"big_thumbs": {"img_url": "https://cover.example/fallback.jpg"}},
        }

        self.assertEqual(
            parse_audio_metadata(video_data),
            {
                "audio_url": "https://audio.example/demo.mp3",
                "cover_url": "https://cover.example/original.jpg",
                "duration": 12345,
                "raw_tags": "#captiontag-atag-b",
                "title": "demo title",
                "video_id": "24680",
            },
        )


if __name__ == "__main__":
    unittest.main()
