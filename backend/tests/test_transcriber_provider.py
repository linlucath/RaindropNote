import builtins
import importlib
import sys
import unittest
from unittest.mock import patch


MODULE_NAME = "app.transcriber.transcriber_provider"


class TestTranscriberProvider(unittest.TestCase):
    def test_import_does_not_probe_mlx_whisper(self):
        original_module = sys.modules.pop(MODULE_NAME, None)
        original_import = builtins.__import__
        attempted_imports = []

        def guarded_import(name, *args, **kwargs):
            if name == "mlx_whisper":
                attempted_imports.append(name)
                raise ImportError("mlx unavailable")
            return original_import(name, *args, **kwargs)

        try:
            with patch("platform.system", return_value="Darwin"), patch(
                "builtins.__import__",
                side_effect=guarded_import,
            ):
                importlib.import_module(MODULE_NAME)
        finally:
            sys.modules.pop(MODULE_NAME, None)
            if original_module is not None:
                sys.modules[MODULE_NAME] = original_module

        self.assertEqual(attempted_imports, [])

    def test_init_transcriber_cache_distinguishes_constructor_arguments(self):
        provider = importlib.import_module(MODULE_NAME)
        original_cache = dict(provider._transcribers)
        created = []

        class FakeTranscriber:
            def __init__(self, *, model_size, device):
                self.model_size = model_size
                self.device = device
                created.append((model_size, device))

        try:
            provider._transcribers.clear()
            first = provider._init_transcriber(
                provider.TranscriberType.FAST_WHISPER,
                FakeTranscriber,
                model_size="base",
                device="cpu",
            )
            second = provider._init_transcriber(
                provider.TranscriberType.FAST_WHISPER,
                FakeTranscriber,
                model_size="large",
                device="cpu",
            )
            third = provider._init_transcriber(
                provider.TranscriberType.FAST_WHISPER,
                FakeTranscriber,
                model_size="base",
                device="cpu",
            )
        finally:
            provider._transcribers.clear()
            provider._transcribers.update(original_cache)

        self.assertIsNot(first, second)
        self.assertIs(first, third)
        self.assertEqual(created, [("base", "cpu"), ("large", "cpu")])

    def test_init_transcriber_accepts_legacy_none_cache_entry(self):
        provider = importlib.import_module(MODULE_NAME)
        original_cache = dict(provider._transcribers)

        class FakeTranscriber:
            pass

        try:
            provider._transcribers[provider.TranscriberType.BCUT] = None

            transcriber = provider._init_transcriber(provider.TranscriberType.BCUT, FakeTranscriber)
        finally:
            provider._transcribers.clear()
            provider._transcribers.update(original_cache)

        self.assertIsInstance(transcriber, FakeTranscriber)


if __name__ == "__main__":
    unittest.main()
