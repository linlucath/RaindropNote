import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock

from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.models.audio_model import AudioDownloadResult
from app.services.note_media_download import download_media


def _audio_meta(title: str = "测试视频") -> AudioDownloadResult:
    return AudioDownloadResult(
        file_path="/tmp/demo.mp3",
        title=title,
        duration=30,
        cover_url=None,
        platform="bilibili",
        video_id="BV123",
        raw_info={"webpage_url": "https://www.bilibili.com/video/BV123"},
    )


class TestNoteMediaDownload(unittest.TestCase):
    def test_cache_hit_returns_cached_audio_without_downloading(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_cache_file = Path(tmp) / "cache-task_audio.json"
            audio_cache_file.write_text(
                json.dumps(asdict(_audio_meta("缓存标题")), ensure_ascii=False),
                encoding="utf-8",
            )
            downloader = Mock()
            update_status = Mock()
            handle_exception = Mock()

            result = download_media(
                downloader=downloader,
                video_url="https://www.bilibili.com/video/BV123",
                quality=DownloadQuality.fast,
                audio_cache_file=audio_cache_file,
                status_phase=TaskStatus.DOWNLOADING,
                platform="bilibili",
                output_path="/tmp",
                screenshot=False,
                video_understanding=False,
                video_interval=0,
                grid_size=[],
                update_status=update_status,
                handle_exception=handle_exception,
            )

        self.assertEqual(result.audio_meta.title, "缓存标题")
        self.assertIsNone(result.video_path)
        self.assertEqual(result.video_img_urls, [])
        update_status.assert_called_once_with("cache-task", TaskStatus.DOWNLOADING)
        downloader.download.assert_not_called()
        downloader.download_video.assert_not_called()
        handle_exception.assert_not_called()

    def test_skip_download_success_writes_metadata_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_cache_file = Path(tmp) / "metadata-task_audio.json"
            audio = _audio_meta("探测标题")
            downloader = Mock()
            downloader.download.return_value = audio

            result = download_media(
                downloader=downloader,
                video_url="https://www.bilibili.com/video/BV123",
                quality=DownloadQuality.medium,
                audio_cache_file=audio_cache_file,
                status_phase=TaskStatus.DOWNLOADING,
                platform="bilibili",
                output_path="/tmp/out",
                screenshot=False,
                video_understanding=False,
                video_interval=0,
                grid_size=[],
                update_status=Mock(),
                handle_exception=Mock(),
                skip_download=True,
            )

            cached = json.loads(audio_cache_file.read_text(encoding="utf-8"))

        self.assertEqual(result.audio_meta, audio)
        self.assertEqual(cached["title"], "探测标题")
        downloader.download.assert_called_once_with(
            video_url="https://www.bilibili.com/video/BV123",
            quality=DownloadQuality.medium,
            output_dir="/tmp/out",
            need_video=False,
            skip_download=True,
        )
        downloader.download_video.assert_not_called()

    def test_video_thumbnail_path_propagates_in_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_cache_file = Path(tmp) / "video-task_audio.json"
            downloader = Mock()
            downloader.download_video.return_value = "/tmp/demo.mp4"
            downloader.download.return_value = _audio_meta()
            video_reader_cls = Mock()
            video_reader = video_reader_cls.return_value
            video_reader.run.return_value = ["/static/screenshots/thumb.jpg"]

            result = download_media(
                downloader=downloader,
                video_url="https://www.bilibili.com/video/BV123",
                quality=DownloadQuality.slow,
                audio_cache_file=audio_cache_file,
                status_phase=TaskStatus.DOWNLOADING,
                platform="bilibili",
                output_path="/tmp/out",
                screenshot=True,
                video_understanding=False,
                video_interval=9,
                grid_size=[],
                update_status=Mock(),
                handle_exception=Mock(),
                video_reader_cls=video_reader_cls,
            )

        self.assertEqual(result.video_path, Path("/tmp/demo.mp4"))
        self.assertEqual(result.video_img_urls, ["/static/screenshots/thumb.jpg"])
        downloader.download_video.assert_called_once_with("https://www.bilibili.com/video/BV123")
        video_reader_cls.assert_called_once_with(
            video_path="/tmp/demo.mp4",
            grid_size=(2, 2),
            frame_interval=9,
            unit_width=960,
            unit_height=540,
            save_quality=80,
        )
        downloader.download.assert_called_once_with(
            video_url="https://www.bilibili.com/video/BV123",
            quality=DownloadQuality.slow,
            output_dir="/tmp/out",
            need_video=True,
        )

    def test_audio_failure_invokes_failure_handler_and_reraises(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_cache_file = Path(tmp) / "failure-task_audio.json"
            downloader = Mock()
            exc = RuntimeError("download failed")
            downloader.download.side_effect = exc
            handle_exception = Mock()

            with self.assertRaises(RuntimeError):
                download_media(
                    downloader=downloader,
                    video_url="https://www.bilibili.com/video/BV123",
                    quality=DownloadQuality.fast,
                    audio_cache_file=audio_cache_file,
                    status_phase=TaskStatus.DOWNLOADING,
                    platform="bilibili",
                    output_path="/tmp/out",
                    screenshot=False,
                    video_understanding=False,
                    video_interval=0,
                    grid_size=[],
                    update_status=Mock(),
                    handle_exception=handle_exception,
                )

        handle_exception.assert_called_once_with("failure-task", exc)


if __name__ == "__main__":
    unittest.main()
