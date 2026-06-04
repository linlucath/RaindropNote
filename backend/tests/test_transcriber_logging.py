import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


TRANSCRIBER_MODULES = [
    "app.transcriber.groq",
    "app.transcriber.kuaishou",
    "app.transcriber.whisper",
]


@pytest.fixture(autouse=True)
def unload_transcriber_modules():
    for module_name in TRANSCRIBER_MODULES:
        sys.modules.pop(module_name, None)
    yield
    for module_name in TRANSCRIBER_MODULES:
        sys.modules.pop(module_name, None)


def stub_module(name, **attrs):
    module = ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def test_whisper_cuda_unavailable_init_does_not_write_stdout(monkeypatch, tmp_path, capsys):
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        stub_module("faster_whisper", WhisperModel=Mock(return_value=object())),
    )
    monkeypatch.setitem(
        sys.modules,
        "modelscope",
        stub_module("modelscope", snapshot_download=Mock()),
    )
    module = importlib.import_module("app.transcriber.whisper")

    model_dir = tmp_path / "models"
    model_path = model_dir / "whisper-base"
    model_path.mkdir(parents=True)
    (model_path / "model.bin").write_bytes(b"model")

    monkeypatch.setattr(module, "get_model_dir", lambda _: str(model_dir))
    monkeypatch.setattr(module, "is_cuda_available", lambda: False)
    monkeypatch.setattr(module, "is_torch_installed", lambda: False)
    monkeypatch.setattr(module, "logger", Mock())

    module.WhisperTranscriber(device="cuda")

    assert capsys.readouterr().out == ""


def test_groq_compression_transcript_does_not_write_stdout(monkeypatch, tmp_path, capsys):
    module = importlib.import_module("app.transcriber.groq")
    audio_path = tmp_path / "input.mp3"
    compressed_path = tmp_path / "compressed.mp3"
    audio_path.write_bytes(b"audio")
    compressed_path.write_bytes(b"compressed")

    transcription = SimpleNamespace(
        text="stdout groq transcript sentinel",
        language="en",
        segments=[
            SimpleNamespace(start=0.0, end=1.0, text=" stdout groq transcript sentinel "),
        ],
        to_dict=lambda: {"text": "stdout groq transcript sentinel"},
    )
    client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(create=Mock(return_value=transcription))
        )
    )

    monkeypatch.setattr(module, "logger", Mock(), raising=False)
    monkeypatch.setattr(module.os.path, "getsize", lambda _: module.MAX_SIZE_BYTES + 1)
    monkeypatch.setattr(module, "compress_audio", Mock(return_value=str(compressed_path)))
    monkeypatch.setattr(
        module.ProviderService,
        "get_provider_by_id",
        Mock(return_value={"api_key": "key", "base_url": "https://example.test"}),
    )
    monkeypatch.setattr(module, "OpenAI", Mock(return_value=client))

    result = module.GroqTranscriber.transcript.__wrapped__(
        module.GroqTranscriber(),
        str(audio_path),
    )

    assert result.full_text == "stdout groq transcript sentinel"
    assert capsys.readouterr().out == ""


def test_kuaishou_submit_result_does_not_write_stdout(monkeypatch, tmp_path, capsys):
    module = importlib.import_module("app.transcriber.kuaishou")
    audio_path = tmp_path / "input.mp3"
    audio_path.write_bytes(b"audio")

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "code": 0,
        "data": {
            "text": [
                {
                    "text": "stdout kuaishou result sentinel",
                    "start_time": 0,
                    "end_time": 1,
                }
            ]
        },
    }

    monkeypatch.setattr(module, "logger", Mock())
    monkeypatch.setattr(module.requests, "post", Mock(return_value=response))

    result = module.KuaishouTranscriber()._submit(str(audio_path))

    assert result["data"]["text"][0]["text"] == "stdout kuaishou result sentinel"
    assert capsys.readouterr().out == ""
