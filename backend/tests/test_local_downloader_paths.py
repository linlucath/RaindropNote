from app.downloaders.local_paths import resolve_local_video_path


def test_resolve_local_video_path_expands_uploads_relative_to_project_root():
    assert resolve_local_video_path(
        "/uploads/demo/video.mp4",
        project_root="/repo/backend",
    ) == "/repo/backend/uploads/demo/video.mp4"


def test_resolve_local_video_path_preserves_non_upload_paths():
    assert resolve_local_video_path(
        "/Users/demo/video.mp4",
        project_root="/repo/backend",
    ) == "/Users/demo/video.mp4"
