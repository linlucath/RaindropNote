from types import SimpleNamespace
from unittest.mock import Mock

from app.transcriber import bcut
from app.transcriber.bcut import BcutTranscriber


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "code": 0,
            "data": {
                "download_url": "https://download.example.test/audio.mp3",
            },
        }


class _TaskResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "code": 0,
            "data": {
                "task_id": "task-secret-id",
            },
        }


def test_commit_upload_does_not_print_response_stdout(capsys):
    transcriber = BcutTranscriber()
    transcriber._BcutTranscriber__in_boss_key = "boss-key"
    transcriber._BcutTranscriber__resource_id = "resource-id"
    transcriber._BcutTranscriber__etags = ["etag-1"]
    transcriber._BcutTranscriber__upload_id = "upload-id"
    transcriber.session = SimpleNamespace(post=lambda *_args, **_kwargs: _Response())

    transcriber._BcutTranscriber__commit_upload()

    assert transcriber._BcutTranscriber__download_url == "https://download.example.test/audio.mp3"
    assert capsys.readouterr().out == ""


def test_commit_upload_does_not_log_download_url(monkeypatch):
    transcriber = BcutTranscriber()
    transcriber._BcutTranscriber__in_boss_key = "boss-key"
    transcriber._BcutTranscriber__resource_id = "resource-id"
    transcriber._BcutTranscriber__etags = ["etag-1"]
    transcriber._BcutTranscriber__upload_id = "upload-id"
    transcriber.session = SimpleNamespace(post=lambda *_args, **_kwargs: _Response())
    logger = Mock()
    monkeypatch.setattr(bcut, "logger", logger)

    transcriber._BcutTranscriber__commit_upload()

    log_output = "\n".join(str(call) for method in logger.method_calls for call in method.args)
    assert "https://download.example.test/audio.mp3" not in log_output


def test_create_task_does_not_log_task_id(monkeypatch):
    transcriber = BcutTranscriber()
    transcriber._BcutTranscriber__download_url = "https://download.example.test/audio.mp3"
    transcriber.session = SimpleNamespace(post=lambda *_args, **_kwargs: _TaskResponse())
    logger = Mock()
    monkeypatch.setattr(bcut, "logger", logger)

    task_id = transcriber._create_task()

    log_output = "\n".join(str(call) for method in logger.method_calls for call in method.args)
    assert task_id == "task-secret-id"
    assert "task-secret-id" not in log_output


def test_transcript_failure_does_not_log_exception_details(monkeypatch):
    transcriber = BcutTranscriber()
    logger = Mock()
    monkeypatch.setattr(bcut, "logger", logger)
    monkeypatch.setattr(
        transcriber,
        "_upload",
        Mock(side_effect=Exception("https://upload.example.test/signed-token")),
    )

    try:
        BcutTranscriber.transcript.__wrapped__(transcriber, "/private/audio.mp3")
    except Exception:
        pass

    log_output = "\n".join(str(call) for method in logger.method_calls for call in method.args)
    assert "https://upload.example.test/signed-token" not in log_output
    assert "/private/audio.mp3" not in log_output
