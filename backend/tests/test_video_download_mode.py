from pathlib import Path
from unittest.mock import Mock
import json
import tempfile

from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.models.audio_model import AudioDownloadResult
from app.services import note_tasks
from app.services.note import NoteGenerator


def _video_audio_meta(video_path: str = "/tmp/BV123-1080p.mp4"):
    return AudioDownloadResult(
        file_path="",
        title="测试视频",
        duration=12,
        cover_url="https://example.test/cover.jpg",
        platform="bilibili",
        video_id="BV123",
        raw_info={"webpage_url": "https://www.bilibili.com/video/BV123"},
        video_path=video_path,
    )


def test_run_note_task_allows_video_download_without_model():
    fake_note = Mock(markdown="# 视频下载完成")
    generator = Mock()
    generator.generate.return_value = fake_note
    executor = Mock()
    executor.run.side_effect = lambda fn: fn()
    save_note = Mock()

    note_tasks.run_note_task(
        task_id="video-task",
        video_url="https://www.bilibili.com/video/BV123",
        platform="bilibili",
        quality=DownloadQuality.fast,
        mode="video_download",
        video_resolution="1080",
        note_generator_factory=Mock(return_value=generator),
        executor_factory=Mock(return_value=executor),
        save_note=save_note,
    )

    generator.generate.assert_called_once()
    assert generator.generate.call_args.kwargs["mode"] == "video_download"
    assert generator.generate.call_args.kwargs["video_resolution"] == "1080"
    save_note.assert_called_once_with("video-task", fake_note, mode="video_download")


def test_note_generator_video_download_mode_skips_transcript_and_gpt_paths():
    generator = NoteGenerator.__new__(NoteGenerator)
    generator.video_img_urls = []
    generator.video_path = None
    generator._update_status = Mock()
    generator._save_metadata = Mock()
    generator._get_gpt = Mock(side_effect=AssertionError("GPT should not be used"))
    generator._summarize_text = Mock(side_effect=AssertionError("summary should not be used"))
    generator._polish_transcript = Mock(side_effect=AssertionError("polish should not be used"))
    generator._download_media = Mock(side_effect=AssertionError("audio media should not be downloaded"))

    downloader = Mock()
    downloader.download_subtitles = Mock(side_effect=AssertionError("subtitles should not be fetched"))
    downloader.download_video.return_value = "/tmp/BV123-1080p.mp4"
    downloader.download.return_value = _video_audio_meta()
    generator._get_downloader = Mock(return_value=downloader)
    generator._build_video_download_audio_meta = Mock(return_value=_video_audio_meta())

    result = generator.generate(
        video_url="https://www.bilibili.com/video/BV123",
        platform="bilibili",
        quality=DownloadQuality.fast,
        task_id="video-task",
        mode="video_download",
        video_resolution="1080",
    )

    assert result is not None
    assert result.markdown == "# 视频下载完成\n\n文件：`/tmp/BV123-1080p.mp4`"
    assert result.transcript is None
    assert result.audio_meta.video_path == "/tmp/BV123-1080p.mp4"
    downloader.download_video.assert_called_once_with(
        "https://www.bilibili.com/video/BV123",
        output_dir=str(Path.home() / "Downloads"),
        resolution="1080",
    )
    generator._build_video_download_audio_meta.assert_called_once_with(
        video_url="https://www.bilibili.com/video/BV123",
        platform="bilibili",
        video_path=Path("/tmp/BV123-1080p.mp4"),
    )
    generator._save_metadata.assert_called_once_with(
        video_id="BV123",
        platform="bilibili",
        task_id="video-task",
    )
    generator._update_status.assert_any_call(
        "video-task",
        TaskStatus.DOWNLOADING,
        platform="bilibili",
    )
    generator._update_status.assert_any_call(
        "video-task",
        TaskStatus.SUCCESS,
        title="测试视频",
        platform="bilibili",
    )


def test_list_saved_tasks_keeps_video_download_results():
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        (output_dir / "video-task.json").write_text(
            json.dumps(
                {
                    "mode": "video_download",
                    "markdown": "# 视频下载完成",
                    "transcript": None,
                    "audio_meta": {
                        "file_path": "",
                        "title": "测试视频",
                        "duration": 0,
                        "cover_url": None,
                        "platform": "bilibili",
                        "video_id": "BV123",
                        "raw_info": {},
                        "video_path": "/tmp/BV123-1080p.mp4",
                    },
                    "video_download": {
                        "file_path": "/tmp/BV123-1080p.mp4",
                        "resolution": "1080",
                        "filename": "BV123-1080p.mp4",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        tasks = note_tasks.list_saved_tasks(output_dir=output_dir)

    assert len(tasks) == 1
    assert tasks[0]["task_id"] == "video-task"
    assert tasks[0]["result"]["mode"] == "video_download"
    assert tasks[0]["result"]["video_download"]["resolution"] == "1080"
