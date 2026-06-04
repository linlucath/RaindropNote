import unittest
from types import SimpleNamespace

from app.services import batch_router_compat


class TestBatchRouterCompat(unittest.TestCase):
    def test_patchable_context_syncs_source_values_and_restores_target(self):
        source = {"requests": "router-requests", "_extract_flat_playlist": "router-extract"}
        target = SimpleNamespace(requests="service-requests", _extract_flat_playlist="service-extract")

        with batch_router_compat.patched_patchables(target, source, source.keys()) as previous:
            self.assertEqual(previous, {
                "requests": "service-requests",
                "_extract_flat_playlist": "service-extract",
            })
            self.assertEqual(target.requests, "router-requests")
            self.assertEqual(target._extract_flat_playlist, "router-extract")

        self.assertEqual(target.requests, "service-requests")
        self.assertEqual(target._extract_flat_playlist, "service-extract")


if __name__ == "__main__":
    unittest.main()
