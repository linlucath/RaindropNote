from unittest.mock import patch

from app.downloaders.kuaishou_downloader import KuaiShouDownloader
from app.downloaders.kuaishou_helper.kuaishou import KuaiShou
from app.downloaders.local_downloader import LocalDownloader
from app.downloaders.youtube_downloader import YoutubeDownloader
from app.models.audio_model import AudioDownloadResult
from app.models.transcriber_model import TranscriptResult


def test_local_download_does_not_write_title_or_path_debug_to_stdout(tmp_path, capsys):
    video_path = tmp_path / "stdout local title.mp4"
    video_path.write_bytes(b"video")
    audio_path = tmp_path / "stdout local title.mp3"
    cover_path = tmp_path / "stdout local cover.jpg"

    downloader = LocalDownloader()

    with (
        patch.object(downloader, "convert_to_mp3", return_value=str(audio_path)) as convert_to_mp3,
        patch.object(downloader, "extract_cover", return_value=str(cover_path)) as extract_cover,
        patch(
            "app.downloaders.local_downloader.save_cover_to_static",
            return_value="/static/covers/stdout-local-cover.jpg",
        ) as save_cover,
    ):
        result = downloader.download(str(video_path))

    assert capsys.readouterr().out == ""
    assert result.file_path == str(audio_path)
    assert result.title == "stdout local title"
    convert_to_mp3.assert_called_once_with(str(video_path))
    extract_cover.assert_called_once_with(str(video_path))
    save_cover.assert_called_once_with(str(cover_path))


def test_kuaishou_download_video_uses_single_download_and_no_stdout(capsys):
    video_path = "/tmp/stdout-kuaishou-video.mp4"
    downloader = KuaiShouDownloader()
    download_result = AudioDownloadResult(
        file_path="/tmp/stdout-kuaishou-audio.mp3",
        title="stdout kuaishou title",
        duration=1,
        cover_url="https://example.test/cover.jpg",
        platform="kuaishou",
        video_id="ks123",
        raw_info={},
        video_path=video_path,
    )

    with patch.object(downloader, "download", return_value=download_result) as download:
        result = downloader.download_video("https://v.kuaishou.com/example", "/tmp/out")

    assert result == video_path
    download.assert_called_once_with("https://v.kuaishou.com/example", "/tmp/out")
    assert capsys.readouterr().out == ""


def test_kuaishou_helper_run_does_not_print_cookie_or_video_details(monkeypatch, capsys):
    helper = KuaiShou()
    video_details = {
        "data": {
            "visionVideoDetail": {
                "status": 1,
                "photo": {
                    "id": "photo123",
                    "caption": "stdout kuaishou helper",
                },
            }
        }
    }

    monkeypatch.setattr(
        "app.downloaders.kuaishou_helper.kuaishou.cfm.get",
        lambda platform: "kuaishou-secret-cookie" if platform == "kuaishou" else None,
    )
    monkeypatch.setattr(helper, "get_photo_id", lambda url: "photo123")
    monkeypatch.setattr(helper, "get_video_details", lambda url, photo_id: video_details)

    result = helper.run("https://v.kuaishou.com/example stdout helper")

    assert result == video_details["data"]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "kuaishou-secret-cookie" not in captured.err
    assert "stdout kuaishou helper" not in captured.err


def test_youtube_download_subtitles_does_not_write_debug_to_stdout(capsys):
    transcript = TranscriptResult(language="en", full_text="", segments=[], raw={})

    with (
        patch("app.downloaders.youtube_downloader.extract_video_id", return_value="yt123"),
        patch("app.downloaders.youtube_downloader.YouTubeSubtitleFetcher") as fetcher_cls,
    ):
        fetcher_cls.return_value.fetch_subtitles.return_value = transcript
        result = YoutubeDownloader().download_subtitles(
            "https://www.youtube.com/watch?v=yt123",
            langs=["en"],
        )

    assert result is transcript
    fetcher_cls.return_value.fetch_subtitles.assert_called_once_with("yt123", ["en"])
    assert capsys.readouterr().out == ""
