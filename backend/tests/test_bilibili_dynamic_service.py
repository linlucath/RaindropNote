import unittest
from unittest.mock import Mock, patch

from app.services.bilibili_dynamic_service import BilibiliDynamicService


class TestBilibiliDynamicService(unittest.TestCase):
    def test_get_video_dynamics_normalizes_only_regular_video_cards(self):
        service = BilibiliDynamicService(lambda _platform: 'SESSDATA=test;')
        response = Mock()
        response.json.return_value = {
            'code': 0,
            'data': {
                'has_more': False,
                'offset': '',
                'items': [
                    {
                        'id_str': 'dynamic-1',
                        'type': 'DYNAMIC_TYPE_AV',
                        'modules': {
                            'module_author': {
                                'name': '作者甲',
                            },
                            'module_dynamic': {
                                'major': {
                                    'type': 'MAJOR_TYPE_ARCHIVE',
                                    'archive': {
                                        'bvid': 'BV1xx411c7mi',
                                        'title': '第一条动态视频',
                                        'jump_url': '//www.bilibili.com/video/BV1xx411c7mi/',
                                        'cover': 'https://example.com/cover.jpg',
                                    },
                                },
                            },
                        },
                    },
                    {
                        'id_str': 'dynamic-2',
                        'type': 'DYNAMIC_TYPE_FORWARD',
                        'modules': {
                            'module_dynamic': {
                                'major': {
                                    'type': 'MAJOR_TYPE_ARCHIVE',
                                    'archive': {
                                        'bvid': 'BV1forward',
                                        'title': '应被忽略的转发视频',
                                    },
                                },
                            },
                        },
                    },
                ],
            },
        }
        response.raise_for_status.return_value = None

        with patch('app.services.bilibili_dynamic_service.requests.get', return_value=response):
            payload = service.get_video_dynamics(page_size=20, offset=None)

        self.assertEqual(payload['items'], [
            {
                'video_id': 'BV1xx411c7mi',
                'video_url': 'https://www.bilibili.com/video/BV1xx411c7mi/',
                'title': '第一条动态视频',
                'author_name': '作者甲',
                'dynamic_id': 'dynamic-1',
                'cover': 'https://example.com/cover.jpg',
            }
        ])
        self.assertFalse(payload['has_more'])
        self.assertEqual(payload['offset'], '')

    def test_get_video_dynamics_uses_last_visible_dynamic_id_as_next_offset(self):
        service = BilibiliDynamicService(lambda _platform: 'SESSDATA=test;')
        response = Mock()
        response.json.return_value = {
            'code': 0,
            'data': {
                'has_more': True,
                'offset': 'server-cursor',
                'items': [
                    {
                        'id_str': 'dynamic-1',
                        'type': 'DYNAMIC_TYPE_AV',
                        'modules': {
                            'module_dynamic': {
                                'major': {
                                    'type': 'MAJOR_TYPE_ARCHIVE',
                                    'archive': {
                                        'bvid': 'BV1visibleA',
                                        'title': '视频 A',
                                    },
                                },
                            },
                        },
                    },
                    {
                        'id_str': 'dynamic-2',
                        'type': 'DYNAMIC_TYPE_AV',
                        'modules': {
                            'module_dynamic': {
                                'major': {
                                    'type': 'MAJOR_TYPE_ARCHIVE',
                                    'archive': {
                                        'bvid': 'BV1visibleB',
                                        'title': '视频 B',
                                    },
                                },
                            },
                        },
                    },
                ],
            },
        }
        response.raise_for_status.return_value = None

        with patch('app.services.bilibili_dynamic_service.requests.get', return_value=response):
            payload = service.get_video_dynamics(page_size=1, offset=None)

        self.assertEqual(
            [item['video_id'] for item in payload['items']],
            ['BV1visibleA'],
        )
        self.assertTrue(payload['has_more'])
        self.assertEqual(payload['offset'], 'dynamic-1')


if __name__ == '__main__':
    unittest.main()
