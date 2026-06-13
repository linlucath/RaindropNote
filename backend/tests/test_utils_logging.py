from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

import requests

from app.utils import logger as logger_utils
from app.utils import url_parser, video_helper


def test_resolve_bilibili_short_url_failure_does_not_print_stdout(capsys):
    with patch(
        "app.utils.url_parser.requests.head",
        side_effect=requests.RequestException("network down"),
    ):
        result = url_parser.resolve_bilibili_short_url("https://b23.tv/demo")

    assert result is None
    assert capsys.readouterr().out == ""


def test_generate_screenshot_does_not_print_command_stdout(tmp_path, capsys):
    with patch(
        "app.utils.video_helper.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stderr=""),
    ):
        output_path = video_helper.generate_screenshot(
            video_path="/tmp/input.mp4",
            output_dir=str(tmp_path),
            timestamp=12,
            index=1,
        )

    assert output_path.startswith(str(tmp_path))
    assert capsys.readouterr().out == ""


def test_generate_screenshot_failure_does_not_print_ffmpeg_stderr(tmp_path, capsys):
    with patch(
        "app.utils.video_helper.subprocess.run",
        return_value=SimpleNamespace(returncode=1, stderr="ffmpeg failed"),
    ):
        output_path = video_helper.generate_screenshot(
            video_path="/tmp/input.mp4",
            output_dir=str(tmp_path),
            timestamp=12,
            index=1,
        )

    assert output_path.startswith(str(tmp_path))
    assert capsys.readouterr().out == ""


def test_build_file_handler_uses_runtime_logs_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(logger_utils, "get_app_dir", lambda subdir="": str(tmp_path / subdir))

    file_handler = logger_utils.build_file_handler()

    assert file_handler is not None
    assert Path(file_handler.baseFilename) == tmp_path / "logs" / "app.log"
