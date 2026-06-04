from app.utils.video_url_rules import extract_video_id_from_url, infer_platform_from_url


def test_infer_platform_from_http_video_hosts():
    assert infer_platform_from_url("https://www.youtube.com/watch?v=abc12345678") == "youtube"
    assert infer_platform_from_url("https://youtu.be/abc12345678") == "youtube"
    assert infer_platform_from_url("https://www.bilibili.com/video/BV1xx411c7mD") == "bilibili"
    assert infer_platform_from_url("https://b23.tv/demo") == "bilibili"
    assert infer_platform_from_url("https://www.douyin.com/video/1234567890") == "douyin"
    assert infer_platform_from_url("https://www.kuaishou.com/short-video/abc") == "kuaishou"


def test_infer_platform_ignores_local_paths_and_unknown_hosts():
    assert infer_platform_from_url("/Users/demo/video.mp4") is None
    assert infer_platform_from_url("file:///tmp/video.mp4") is None
    assert infer_platform_from_url("https://example.com/video/BV1xx411c7mD") is None


def test_extract_video_id_from_url_matches_supported_platform_rules():
    assert extract_video_id_from_url("https://www.bilibili.com/video/BV1xx411c7mD", "bilibili") == "BV1xx411c7mD"
    assert extract_video_id_from_url("https://www.youtube.com/watch?v=abc12345678", "youtube") == "abc12345678"
    assert extract_video_id_from_url("https://youtu.be/abc12345678", "youtube") == "abc12345678"
    assert extract_video_id_from_url("https://www.douyin.com/video/1234567890", "douyin") == "1234567890"
    assert extract_video_id_from_url("https://www.kuaishou.com/short-video/abc", "kuaishou") is None
