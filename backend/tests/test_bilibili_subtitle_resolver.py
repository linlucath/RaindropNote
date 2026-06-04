import unittest

from app.downloaders.bilibili_subtitle_resolver import (
    build_bilibili_subtitle_file,
    choose_bilibili_subtitle,
)


class TestBilibiliSubtitleResolver(unittest.TestCase):
    def test_choose_bilibili_subtitle_prefers_requested_language_order(self):
        subtitles = {
            'en': {'ext': 'srt'},
            'ai-zh': {'ext': 'json3'},
            'zh': {'ext': 'srt'},
        }

        selection = choose_bilibili_subtitle(subtitles, ['zh-Hans', 'ai-zh', 'en'])

        self.assertIsNotNone(selection)
        self.assertEqual(selection.language, 'ai-zh')
        self.assertEqual(selection.info, {'ext': 'json3'})

    def test_choose_bilibili_subtitle_falls_back_to_first_non_danmaku_language(self):
        subtitles = {
            'danmaku': {'ext': 'xml'},
            'fr': {'ext': 'srt'},
            'en': {'ext': 'srt'},
        }

        selection = choose_bilibili_subtitle(subtitles, ['zh'])

        self.assertIsNotNone(selection)
        self.assertEqual(selection.language, 'fr')
        self.assertEqual(selection.info, {'ext': 'srt'})

    def test_choose_bilibili_subtitle_returns_none_for_empty_or_danmaku_only_payload(self):
        self.assertIsNone(choose_bilibili_subtitle({}, ['zh']))
        self.assertIsNone(choose_bilibili_subtitle({'danmaku': {'ext': 'xml'}}, ['zh']))

    def test_build_bilibili_subtitle_file_defaults_to_srt_extension(self):
        subtitle_file = build_bilibili_subtitle_file('/tmp/subs', 'BV123', 'ai-zh', {})

        self.assertEqual(subtitle_file, '/tmp/subs/BV123.ai-zh.srt')


if __name__ == '__main__':
    unittest.main()
