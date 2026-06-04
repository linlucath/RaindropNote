from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.services.provider import ProviderService


def _provider(**overrides):
    values = {
        "id": "provider-1",
        "name": "Demo Provider",
        "logo": "custom",
        "type": "openai",
        "api_key": "sk-1234567890",
        "base_url": "https://api.example.test/v1",
        "enabled": 1,
        "created_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class TestProviderService(unittest.TestCase):
    def test_serialize_provider_preserves_api_key_and_safe_masks_it(self):
        row = _provider(api_key="sk-1234567890")

        raw = ProviderService.serialize_provider(row)
        safe = ProviderService.serialize_provider_safe(row)

        self.assertEqual(raw["api_key"], "sk-1234567890")
        self.assertEqual(safe["api_key"], "sk-1*****7890")

    def test_add_provider_uses_injected_id_and_insert_provider(self):
        insert_provider = Mock(return_value="provider-new")

        result = ProviderService.add_provider(
            name="Demo",
            api_key="sk-demo",
            base_url="https://api.example.test/v1",
            logo="ignored-logo",
            type_="openai",
            enabled=1,
            id_factory=lambda: "PROVIDER-NEW",
            insert_provider_fn=insert_provider,
            log=Mock(),
        )

        self.assertEqual(result, "provider-new")
        insert_provider.assert_called_once_with(
            "provider-new",
            "Demo",
            "sk-demo",
            "https://api.example.test/v1",
            "custom",
            "openai",
            1,
        )

    def test_add_provider_uses_runtime_insert_provider_patch_by_default(self):
        insert_provider = Mock(return_value="provider-runtime")

        with patch("app.services.provider.insert_provider", insert_provider):
            result = ProviderService.add_provider(
                name="Demo",
                api_key="sk-demo",
                base_url="https://api.example.test/v1",
                logo=None,
                type_="openai",
                id_factory=lambda: "PROVIDER-RUNTIME",
                log=Mock(),
            )

        self.assertEqual(result, "provider-runtime")
        insert_provider.assert_called_once()

    def test_get_provider_by_id_uses_runtime_lookup(self):
        lookup = Mock(return_value=_provider(id="provider-runtime"))

        result = ProviderService.get_provider_by_id("provider-runtime", provider_lookup=lookup)

        self.assertEqual(result["id"], "provider-runtime")
        lookup.assert_called_once_with("provider-runtime")

    def test_get_provider_by_id_uses_runtime_lookup_patch_by_default(self):
        lookup = Mock(return_value=_provider(id="provider-runtime"))

        with patch("app.services.provider.get_provider_record_by_id", lookup):
            result = ProviderService.get_provider_by_id("provider-runtime")

        self.assertEqual(result["id"], "provider-runtime")
        lookup.assert_called_once_with("provider-runtime")

    def test_update_provider_filters_empty_fields_and_uses_injected_update(self):
        update_provider = Mock()

        result = ProviderService.update_provider(
            "provider-1",
            {
                "id": "provider-1",
                "name": "Demo",
                "api_key": None,
                "base_url": "https://api.example.test/v2",
            },
            update_provider_fn=update_provider,
            log=Mock(),
        )

        self.assertEqual(result, "provider-1")
        update_provider.assert_called_once_with(
            "provider-1",
            name="Demo",
            base_url="https://api.example.test/v2",
        )


if __name__ == "__main__":
    unittest.main()
