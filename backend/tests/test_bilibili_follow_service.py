import unittest
from unittest.mock import Mock, patch

from app.services.bilibili_follow_service import BilibiliFollowService


class TestBilibiliFollowService(unittest.TestCase):
    def test_get_followings_returns_low_resolution_avatar_url(self):
        service = BilibiliFollowService(lambda _platform: 'DedeUserID=12345;')
        response = Mock()
        response.json.return_value = {
            'code': 0,
            'data': {
                'list': [
                    {
                        'mid': 1,
                        'uname': '测试UP',
                        'face': 'http://i0.hdslb.com/bfs/face/avatar.jpg',
                        'sign': 'hello',
                    }
                ],
                'total': 1,
            },
        }
        response.raise_for_status.return_value = None

        with patch('app.services.bilibili_follow_service.requests.get', return_value=response):
            payload = service.get_followings(page=1, page_size=20)

        self.assertEqual(payload['items'], [
            {
                'mid': '1',
                'name': '测试UP',
                'avatar_url': 'https://i0.hdslb.com/bfs/face/avatar.jpg@96w_96h_1c_1s.webp',
                'sign': 'hello',
            }
        ])

    def test_get_followings_accepts_injected_request_get(self):
        calls = []
        response = Mock()
        response.json.return_value = {
            'code': 0,
            'data': {
                'list': [],
                'total': 0,
            },
        }
        response.raise_for_status.return_value = None

        def request_get(url, **kwargs):
            calls.append({'url': url, **kwargs})
            return response

        service = BilibiliFollowService(
            lambda _platform: 'DedeUserID=12345;',
            request_get=request_get,
        )

        payload = service.get_followings(page=1, page_size=20)

        self.assertEqual(payload['items'], [])
        self.assertEqual(calls[0]['headers']['Cookie'], 'DedeUserID=12345;')
        self.assertEqual(calls[0]['headers']['Referer'], 'https://space.bilibili.com/')


if __name__ == '__main__':
    unittest.main()
