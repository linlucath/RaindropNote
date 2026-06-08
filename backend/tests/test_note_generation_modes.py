import pytest

from app.services import note_tasks


def test_normalize_generation_mode_accepts_video_download_mode():
    assert note_tasks.normalize_generation_mode(None) == "polished_transcript"
    assert note_tasks.normalize_generation_mode("polished_transcript") == "polished_transcript"
    assert note_tasks.normalize_generation_mode(" video_download ") == "video_download"


def test_normalize_generation_mode_rejects_unsupported_modes():
    with pytest.raises(note_tasks.NoteTaskValidationError) as exc:
        note_tasks.normalize_generation_mode("note")

    assert exc.value.status_code == 400
    assert exc.value.detail == "不支持的任务模式"


def test_normalize_video_resolution_accepts_supported_values():
    assert note_tasks.normalize_video_resolution(None) == "best"
    assert note_tasks.normalize_video_resolution("") == "best"
    assert note_tasks.normalize_video_resolution(" best ") == "best"
    assert note_tasks.normalize_video_resolution("2160") == "2160"
    assert note_tasks.normalize_video_resolution("1080") == "1080"
    assert note_tasks.normalize_video_resolution("720") == "720"
    assert note_tasks.normalize_video_resolution("480") == "480"
    assert note_tasks.normalize_video_resolution("360") == "360"


def test_normalize_video_resolution_rejects_unsupported_values():
    with pytest.raises(note_tasks.NoteTaskValidationError) as exc:
        note_tasks.normalize_video_resolution("1440")

    assert exc.value.status_code == 400
    assert exc.value.detail == "不支持的视频分辨率"
