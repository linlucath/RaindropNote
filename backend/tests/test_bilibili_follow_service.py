import unittest
from unittest.mock import Mock, patch

from app.services.bilibili_follow_service import BilibiliFollowService


class TestBilibiliFollowService(unittest.TestCase):
    def test_get_followings_drops_avatar_fields_from_items(self):
        service = BilibiliFollowService(lambda _platform: 'DedeUserID=12345;')
        response = Mock()
        response.json.return_value = {
            'code': 0,
            'data': {
                'list': [
                    {
                        'mid': 1,
                        'uname': '测试UP',
                        'face': 'https://example.com/avatar.jpg',
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
                'sign': 'hello',
            }
        ])


if __name__ == '__main__':
    unittest.main()
