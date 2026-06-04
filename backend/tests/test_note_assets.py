import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app.services.note_assets import fetch_image_proxy, save_uploaded_file


class FakeUploadFile:
    def __init__(self, filename: str, payload: bytes):
        self.filename = filename
        self._payload = payload

    async def read(self):
        return self._payload


class FakeImageResponse:
    def __init__(self, status_code: int = 200, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class FakeAsyncClient:
    def __init__(self, response: FakeImageResponse, calls: list, timeout: float):
        self._response = response
        self._calls = calls
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, headers: dict):
        self._calls.append({"url": url, "headers": headers, "timeout": self.timeout})
        return self._response


def make_client_factory(response: FakeImageResponse, calls: list):
    def client_factory(*, timeout: float):
        return FakeAsyncClient(response, calls, timeout)

    return client_factory


class TestNoteAssets(unittest.IsolatedAsyncioTestCase):
    async def test_save_uploaded_file_creates_upload_dir_and_writes_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp) / "uploads"
            upload_file = FakeUploadFile("clip.mp4", b"video-bytes")

            result = await save_uploaded_file(upload_file, upload_dir=upload_dir)

            self.assertEqual(result.url, "/uploads/clip.mp4")
            self.assertEqual((upload_dir / "clip.mp4").read_bytes(), b"video-bytes")

    async def test_fetch_image_proxy_success_uses_headers_timeout_and_streams_content(self):
        calls = []
        response = FakeImageResponse(
            headers={"Content-Type": "image/png"},
            chunks=[b"first", b"second"],
        )

        result = await fetch_image_proxy(
            "https://example.test/image.png",
            user_agent="Browser UA",
            client_factory=make_client_factory(response, calls),
        )

        self.assertEqual(
            calls,
            [
                {
                    "url": "https://example.test/image.png",
                    "headers": {
                        "Referer": "https://www.bilibili.com/",
                        "User-Agent": "Browser UA",
                    },
                    "timeout": 10.0,
                }
            ],
        )
        self.assertEqual(result.media_type, "image/png")
        self.assertEqual(
            result.headers,
            {
                "Cache-Control": "public, max-age=86400",
                "Content-Type": "image/png",
            },
        )
        self.assertEqual([chunk async for chunk in result.body], [b"first", b"second"])

    async def test_fetch_image_proxy_uses_runtime_httpx_async_client_patch_by_default(self):
        calls = []
        response = FakeImageResponse(
            headers={"Content-Type": "image/webp"},
            chunks=[b"image-bytes"],
        )
        client_factory = make_client_factory(response, calls)

        with unittest.mock.patch("app.services.note_assets.httpx.AsyncClient", client_factory):
            result = await fetch_image_proxy(
                "https://example.test/runtime.webp",
                user_agent="Runtime UA",
            )

        self.assertEqual(result.media_type, "image/webp")
        self.assertEqual([chunk async for chunk in result.body], [b"image-bytes"])
        self.assertEqual(calls[0]["url"], "https://example.test/runtime.webp")
        self.assertEqual(calls[0]["headers"]["User-Agent"], "Runtime UA")

    async def test_fetch_image_proxy_non_200_raises_proxy_error(self):
        calls = []
        response = FakeImageResponse(status_code=403)

        with self.assertRaises(HTTPException) as ctx:
            await fetch_image_proxy(
                "https://example.test/blocked.jpg",
                user_agent="Browser UA",
                client_factory=make_client_factory(response, calls),
            )

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.detail, "403: 图片获取失败")


if __name__ == "__main__":
    unittest.main()
