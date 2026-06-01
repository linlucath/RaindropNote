import unittest
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from app import create_app


class TestConfigRouterCleanup(unittest.TestCase):
    def test_transcriber_management_routes_are_removed(self):
        @asynccontextmanager
        async def lifespan(_app):
            yield

        app = create_app(lifespan=lifespan)
        client = TestClient(app)

        for path in (
            "/api/transcriber_config",
            "/api/transcriber_models_status",
            "/api/transcriber_download",
        ):
            with self.subTest(path=path):
                response = client.get(path) if path != "/api/transcriber_download" else client.post(
                    path,
                    json={"model_size": "small"},
                )
                self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
