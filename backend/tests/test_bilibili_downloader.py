import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from app.downloaders.bilibili_downloader import BilibiliDownloader


class _FakeYoutubeDL:
    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, video_url, download=True):
        if not self.opts.get('noplaylist'):
            raise AssertionError('download_subtitles should force noplaylist for multi-part BV videos')
        return {
            'requested_subtitles': {
                'ai-zh': {
                    'ext': 'srt',
                    'data': (
                        '1\n'
                        '00:00:00,000 --> 00:00:01,000\n'
                        '第一句字幕\n\n'
                        '2\n'
                        '00:00:01,000 --> 00:00:02,000\n'
                        '第二句字幕\n'
                    ),
                }
            }
        }


class TestBilibiliDownloader(unittest.TestCase):
    @patch('app.downloaders.bilibili_downloader._apply_bilibili_ydl_defaults', side_effect=lambda opts: opts)
    @patch('app.downloaders.bilibili_downloader.yt_dlp.YoutubeDL', side_effect=_FakeYoutubeDL)
    def test_download_subtitles_forces_single_video_extraction(self, _ydl_cls, _apply_defaults):
        downloader = BilibiliDownloader()

        with tempfile.TemporaryDirectory() as tmp:
            result = downloader.download_subtitles(
                'https://www.bilibili.com/video/BV1bDCrBrEUP',
                output_dir=tmp,
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.language, 'ai-zh')
        self.assertEqual([segment.text for segment in result.segments], ['第一句字幕', '第二句字幕'])
        self.assertEqual(result.raw, {'source': 'bilibili_subtitle', 'format': 'srt'})

    def test_download_keeps_legacy_private_defaults_wrapper_path(self):
        captured_opts = []

        class FakeYoutubeDL:
            def __init__(self, opts):
                captured_opts.append(opts)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, video_url, download=True):
                return {
                    'id': 'BV1bDCrBrEUP',
                    'title': '测试视频',
                    'duration': 12,
                    'thumbnail': 'https://example.test/cover.jpg',
                }

        def apply_defaults(opts):
            return {**opts, 'legacy_wrapper_marker': True}

        downloader = BilibiliDownloader()

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                'app.downloaders.bilibili_downloader._apply_bilibili_ydl_defaults',
                side_effect=apply_defaults,
            ):
                with patch(
                    'app.downloaders.bilibili_downloader.yt_dlp.YoutubeDL',
                    side_effect=FakeYoutubeDL,
                ):
                    result = downloader.download(
                        'https://www.bilibili.com/video/BV1bDCrBrEUP',
                        output_dir=tmp,
                        skip_download=True,
                    )

        self.assertEqual(result.video_id, 'BV1bDCrBrEUP')
        self.assertEqual(result.file_path, '')
        self.assertEqual(len(captured_opts), 1)
        self.assertTrue(captured_opts[0]['legacy_wrapper_marker'])

    def test_download_video_cached_path_does_not_print_debug_output(self):
        downloader = BilibiliDownloader()

        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / 'BV1bDCrBrEUP.mp4'
            video_path.write_bytes(b'cached video')

            stdout = StringIO()
            with redirect_stdout(stdout):
                result = downloader.download_video(
                    'https://www.bilibili.com/video/BV1bDCrBrEUP',
                    output_dir=tmp,
                )

        self.assertEqual(result, str(video_path))
        self.assertEqual(stdout.getvalue(), '')

    def test_download_video_passes_resolution_to_video_options_builder(self):
        captured_resolution = []

        class FakeYoutubeDL:
            def __init__(self, opts):
                self.opts = opts

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, video_url, download=True):
                Path(
                    self.opts['outtmpl']
                    .replace('%(id)s', 'BV1bDCrBrEUP')
                    .replace('%(ext)s', 'mp4')
                ).write_bytes(b'video')
                return {'id': 'BV1bDCrBrEUP'}

        def build_video_opts(output_path, *, resolution=None):
            captured_resolution.append(resolution)
            return {'outtmpl': output_path, 'noplaylist': True}

        downloader = BilibiliDownloader()

        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                'app.downloaders.bilibili_downloader.build_video_ydl_opts',
                side_effect=build_video_opts,
            ), patch(
                'app.downloaders.bilibili_downloader._apply_bilibili_ydl_defaults',
                side_effect=lambda opts: opts,
            ), patch(
                'app.downloaders.bilibili_downloader.yt_dlp.YoutubeDL',
                side_effect=FakeYoutubeDL,
            ):
                result = downloader.download_video(
                    'https://www.bilibili.com/video/BV1bDCrBrEUP',
                    output_dir=tmp,
                    resolution='1080',
                )

        self.assertEqual(captured_resolution, ['1080'])
        self.assertTrue(result.endswith('BV1bDCrBrEUP-1080p.mp4'))

    def test_parse_json3_subtitle_keeps_legacy_file_wrapper_behavior(self):
        downloader = BilibiliDownloader()

        with tempfile.TemporaryDirectory() as tmp:
            subtitle_file = Path(tmp) / 'BV1bDCrBrEUP.ai-zh.json3'
            subtitle_file.write_text(
                json.dumps(
                    {
                        'events': [
                            {
                                'tStartMs': 1000,
                                'dDurationMs': 1500,
                                'segs': [{'utf8': '第一'}, {'utf8': '句'}],
                            },
                            {
                                'tStartMs': 3000,
                                'dDurationMs': 1000,
                                'segs': [{'utf8': '第二句'}],
                            },
                        ]
                    }
                ),
                encoding='utf-8',
            )

            result = downloader._parse_json3_subtitle(str(subtitle_file), 'ai-zh')

        self.assertIsNotNone(result)
        self.assertEqual(result.language, 'ai-zh')
        self.assertEqual(result.full_text, '第一句 第二句')
        self.assertEqual(
            [(segment.start, segment.end, segment.text) for segment in result.segments],
            [(1.0, 2.5, '第一句'), (3.0, 4.0, '第二句')],
        )
        self.assertEqual(result.raw, {'source': 'bilibili_subtitle', 'file': str(subtitle_file)})


if __name__ == '__main__':
    unittest.main()
