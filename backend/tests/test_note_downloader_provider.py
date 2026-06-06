import unittest
from unittest.mock import Mock

from app.enmus.exception import NoteErrorEnum
from app.exceptions.note import NoteError
from app.services.note_downloader_provider import build_downloader


class TestNoteDownloaderProvider(unittest.TestCase):
    def test_build_downloader_returns_configured_downloader(self):
        log = Mock()
        downloader = object()

        result = build_downloader("demo", platform_map={"demo": downloader}, log=log)

        self.assertIs(result, downloader)
        log.info.assert_called_once_with(f"使用下载器：{downloader.__class__}")

    def test_build_downloader_raises_note_error_for_unsupported_platform(self):
        log = Mock()

        with self.assertRaises(NoteError) as ctx:
            build_downloader("unknown", platform_map={}, log=log)

        self.assertEqual(ctx.exception.code, NoteErrorEnum.PLATFORM_NOT_SUPPORTED.code)
        self.assertEqual(ctx.exception.message, NoteErrorEnum.PLATFORM_NOT_SUPPORTED.message)
        log.error.assert_called_once_with("不支持的平台：unknown")


if __name__ == "__main__":
    unittest.main()
