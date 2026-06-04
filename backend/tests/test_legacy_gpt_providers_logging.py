from unittest.mock import Mock

import pytest

from app.models.transcriber_model import TranscriptSegment


class DummyOpenAIClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.chat = Mock()


@pytest.mark.parametrize(
    ("module_path", "class_name", "model_env", "model_name", "provider_name"),
    [
        (
            "app.gpt.openai_gpt",
            "OpenaiGPT",
            "OPENAI_MODEL",
            "stdout-openai-model",
            "OpenAICompatibleProvider",
        ),
        (
            "app.gpt.qwen_gpt",
            "QwenGPT",
            "QWEN_MODEL",
            "stdout-qwen-model",
            "OpenAICompatibleProvider",
        ),
    ],
)
def test_compatible_provider_init_and_create_messages_do_not_write_stdout(
    monkeypatch,
    capsys,
    module_path,
    class_name,
    model_env,
    model_name,
    provider_name,
):
    module = pytest.importorskip(module_path)
    provider = Mock()
    monkeypatch.setattr(module, provider_name, provider)
    monkeypatch.setenv(model_env, model_name)

    gpt = getattr(module, class_name)()
    gpt.screenshot = True
    if hasattr(gpt, "link"):
        gpt.link = True

    messages = gpt.create_messages(
        [TranscriptSegment(start=3, end=5, text="stdout transcript sentinel")],
        "stdout title sentinel",
        "stdout tag sentinel",
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert model_name not in captured.out
    assert "stdout transcript sentinel" not in captured.out
    assert ":需要截图" not in captured.out
    assert ":需要链接" not in captured.out
    assert messages[0]["role"] == "user"
    assert "stdout transcript sentinel" in messages[0]["content"]
    provider.assert_called_once()


def test_deepseek_init_and_create_messages_do_not_write_stdout(monkeypatch, capsys):
    module = pytest.importorskip("app.gpt.deepseek_gpt")
    monkeypatch.setattr(module, "OpenAI", DummyOpenAIClient)
    monkeypatch.setenv("DEEP_SEEK_MODEL", "stdout-deepseek-model")

    gpt = module.DeepSeekGPT()
    gpt.screenshot = True

    messages = gpt.create_messages(
        [TranscriptSegment(start=7, end=9, text="stdout deepseek transcript sentinel")],
        "stdout deepseek title sentinel",
        "stdout deepseek tag sentinel",
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "stdout-deepseek-model" not in captured.out
    assert "stdout deepseek transcript sentinel" not in captured.out
    assert ":需要截图" not in captured.out
    assert messages[0]["role"] == "user"
    assert "stdout deepseek transcript sentinel" in messages[0]["content"]
