import os
import unittest
from unittest.mock import patch

from app.transcriber.transcriber_provider import get_transcriber


class TestTranscriberProviderConfig(unittest.TestCase):
    def test_explicit_model_size_takes_precedence_over_environment_default(self):
        old_value = os.environ.get("WHISPER_MODEL_SIZE")
        os.environ["WHISPER_MODEL_SIZE"] = "medium"
        try:
            with patch("app.transcriber.transcriber_provider.get_whisper_transcriber", return_value=object()) as get_whisper:
                get_transcriber(transcriber_type="fast-whisper", model_size="tiny")
        finally:
            if old_value is None:
                os.environ.pop("WHISPER_MODEL_SIZE", None)
            else:
                os.environ["WHISPER_MODEL_SIZE"] = old_value

        get_whisper.assert_called_once_with("tiny", device="cuda")


if __name__ == "__main__":
    unittest.main()
