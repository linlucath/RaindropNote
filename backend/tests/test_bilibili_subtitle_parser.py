import unittest

from app.downloaders.bilibili_subtitle_parser import (
    parse_bilibili_json_transcript,
    parse_srt_transcript,
)


class TestBilibiliSubtitleParser(unittest.TestCase):
    def test_parse_srt_transcript_converts_timestamps_filters_empty_text_and_preserves_raw(self):
        srt_content = (
            '1\n'
            '00:00:01,500 --> 00:00:03,000\n'
            '第一句字幕\n\n'
            '2\n'
            '00:00:03,000 --> 00:00:04,000\n'
            '   \n\n'
            '3\n'
            '00:01:02,250 --> 00:01:04,750\n'
            '第二句字幕\n'
        )

        result = parse_srt_transcript(srt_content, language='zh-Hans')

        self.assertIsNotNone(result)
        self.assertEqual(result.language, 'zh-Hans')
        self.assertEqual(result.full_text, '第一句字幕 第二句字幕')
        self.assertEqual(
            [(segment.start, segment.end, segment.text) for segment in result.segments],
            [
                (1.5, 3.0, '第一句字幕'),
                (62.25, 64.75, '第二句字幕'),
            ],
        )
        self.assertEqual(result.raw, {'source': 'bilibili_subtitle', 'format': 'srt'})

    def test_parse_bilibili_json_transcript_converts_milliseconds_filters_empty_text_and_preserves_raw(self):
        subtitle_data = {
            'events': [
                {
                    'tStartMs': 1500,
                    'dDurationMs': 1250,
                    'segs': [{'utf8': '第一'}, {'utf8': '句字幕'}],
                },
                {
                    'tStartMs': 3000,
                    'dDurationMs': 500,
                    'segs': [{'utf8': '   '}],
                },
                {
                    'tStartMs': 62000,
                    'dDurationMs': 2750,
                    'segs': [{'utf8': '第二句字幕'}],
                },
            ]
        }

        result = parse_bilibili_json_transcript(
            subtitle_data,
            language='ai-zh',
            raw={'source': 'bilibili_subtitle', 'file': '/tmp/demo.ai-zh.json3'},
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.language, 'ai-zh')
        self.assertEqual(result.full_text, '第一句字幕 第二句字幕')
        self.assertEqual(
            [(segment.start, segment.end, segment.text) for segment in result.segments],
            [
                (1.5, 2.75, '第一句字幕'),
                (62.0, 64.75, '第二句字幕'),
            ],
        )
        self.assertEqual(
            result.raw,
            {'source': 'bilibili_subtitle', 'file': '/tmp/demo.ai-zh.json3'},
        )

    def test_parse_srt_transcript_returns_none_when_no_text_segments(self):
        srt_content = (
            '1\n'
            '00:00:00,000 --> 00:00:01,000\n'
            '   \n'
        )

        self.assertIsNone(parse_srt_transcript(srt_content, language='zh'))

    def test_parse_bilibili_json_transcript_returns_none_when_no_text_segments(self):
        subtitle_data = {
            'events': [
                {'tStartMs': 0, 'dDurationMs': 1000, 'segs': [{'utf8': '   '}]},
            ]
        }

        self.assertIsNone(parse_bilibili_json_transcript(subtitle_data, language='zh'))


if __name__ == '__main__':
    unittest.main()
