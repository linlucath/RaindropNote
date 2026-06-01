import unittest
from unittest.mock import patch

from app.services.note import NoteGenerator


class TestNoteGeneratorTranscriberConfig(unittest.TestCase):
    def test_init_does_not_load_transcriber_configuration(self):
        with patch("app.services.note.TranscriberConfigManager", create=True) as config_manager:
            generator = NoteGenerator()

        self.assertIsNone(generator.video_path)
        self.assertEqual(generator.video_img_urls, [])
        config_manager.assert_not_called()


if __name__ == "__main__":
    unittest.main()
