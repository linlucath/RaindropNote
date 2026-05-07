import unittest
from unittest.mock import patch

from app.services.note import NoteGenerator


class TestNoteGeneratorTranscriberConfig(unittest.TestCase):
    def test_init_transcriber_uses_configured_model_size(self):
        generator = NoteGenerator.__new__(NoteGenerator)
        generator.transcriber_type = "fast-whisper"
        generator.model_size = "tiny"

        with (
            patch("app.services.note._get_transcriber_registry", return_value={"fast-whisper": None}),
            patch("app.services.note._get_configured_transcriber", return_value=object()) as get_transcriber,
        ):
            generator._init_transcriber()

        get_transcriber.assert_called_once_with(
            transcriber_type="fast-whisper",
            model_size="tiny",
        )


if __name__ == "__main__":
    unittest.main()
