import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import create_app


class TestBilibiliRouter(unittest.TestCase):
    def setUp(self):
        self.app = create_app(lifespan=None)
        self.client = TestClient(self.app)

    def test_followings_requires_bilibili_cookie(self):
        with patch('app.routers.bilibili.follow_service.get_followings', side_effect=ValueError('请先在设置页填写 Bilibili Cookie')):
            response = self.client.get('/api/bilibili/followings')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotEqual(payload['code'], 0)
        self.assertIn('Cookie', payload['msg'])

    def test_followings_returns_paginated_items(self):
        with patch('app.routers.bilibili.follow_service.get_followings', return_value={
            'items': [{'mid': '1', 'name': '测试UP', 'sign': 'hello'}],
            'page': 2,
            'page_size': 10,
            'has_more': False,
            'total': 1,
        }) as get_followings:
            response = self.client.get('/api/bilibili/followings?page=2&page_size=10&keyword=test')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)
        self.assertIn('items', payload['data'])
        self.assertEqual(payload['data']['page'], 2)
        self.assertEqual(payload['data']['page_size'], 10)
        get_followings.assert_called_once_with(page=2, page_size=10)

    def test_uploader_videos_requires_mid(self):
        response = self.client.get('/api/bilibili/uploader_videos')

        self.assertEqual(response.status_code, 422)

    def test_uploader_videos_returns_normalized_batch_videos(self):
        with patch('app.routers.bilibili.preview_bilibili_space_page', return_value={
            'items': [
                {
                    'video_id': 'BV1xx',
                    'video_url': 'https://www.bilibili.com/video/BV1xx',
                    'title': '视频1',
                    'view_count': 123456,
                }
            ],
            'page': 2,
            'page_size': 10,
            'has_more': True,
            'total': None,
        }) as preview:
            response = self.client.get('/api/bilibili/uploader_videos?mid=558268687&page=2&page_size=10&limit=20')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['page'], 2)
        self.assertEqual(payload['data']['page_size'], 10)
        self.assertTrue(payload['data']['has_more'])
        self.assertIn('video_id', payload['data']['items'][0])
        self.assertIn('video_url', payload['data']['items'][0])
        self.assertEqual(payload['data']['items'][0]['view_count'], 123456)
        preview.assert_called_once_with(
            'https://space.bilibili.com/558268687/upload/video',
            page=2,
            page_size=10,
            limit=20,
        )

    def test_dynamics_requires_bilibili_cookie(self):
        with patch('app.routers.bilibili.dynamic_service.get_video_dynamics', side_effect=ValueError('请先在设置页填写 Bilibili Cookie')):
            response = self.client.get('/api/bilibili/dynamics')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertNotEqual(payload['code'], 0)
        self.assertIn('Cookie', payload['msg'])

    def test_dynamics_returns_paginated_items(self):
        with patch('app.routers.bilibili.dynamic_service.get_video_dynamics', return_value={
            'items': [
                {
                    'video_id': 'BV1dynamicA',
                    'video_url': 'https://www.bilibili.com/video/BV1dynamicA',
                    'title': '第一条动态视频',
                    'author_name': '作者甲',
                }
            ],
            'offset': 'dynamic-1',
            'page_size': 10,
            'has_more': True,
        }) as get_video_dynamics:
            response = self.client.get('/api/bilibili/dynamics?offset=dynamic-0&page_size=10')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['offset'], 'dynamic-1')
        self.assertEqual(payload['data']['page_size'], 10)
        self.assertTrue(payload['data']['has_more'])
        self.assertEqual(payload['data']['items'][0]['author_name'], '作者甲')
        get_video_dynamics.assert_called_once_with(page_size=10, offset='dynamic-0')


if __name__ == '__main__':
    unittest.main()
