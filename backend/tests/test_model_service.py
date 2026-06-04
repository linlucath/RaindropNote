import unittest
from unittest.mock import Mock

from app.models.model_config import ModelConfig
from app.services.model import ModelService


class TestModelService(unittest.TestCase):
    def test_get_model_list_returns_empty_when_provider_missing(self):
        factory = Mock()
        log = Mock()

        result = ModelService.get_model_list(
            "missing-provider",
            provider_lookup=Mock(return_value=None),
            factory=factory,
            log=log,
        )

        self.assertEqual(result, [])
        factory.from_config.assert_not_called()

    def test_get_model_list_uses_injected_provider_and_factory(self):
        provider = {
            "id": "provider-1",
            "name": "Demo Provider",
            "api_key": "sk-demo",
            "base_url": "https://api.example.test/v1",
        }
        gpt = Mock()
        gpt.list_models.return_value = ["gpt-demo", "gpt-small"]
        factory = Mock()
        factory.from_config.return_value = gpt

        result = ModelService.get_model_list(
            "provider-1",
            provider_lookup=Mock(return_value=provider),
            factory=factory,
            log=Mock(),
        )

        self.assertEqual(result, ["gpt-demo", "gpt-small"])
        factory.from_config.assert_called_once()
        config = factory.from_config.call_args.args[0]
        self.assertIsInstance(config, ModelConfig)
        self.assertEqual(config.api_key, "sk-demo")
        self.assertEqual(config.base_url, "https://api.example.test/v1")
        self.assertEqual(config.provider, "Demo Provider")
        self.assertEqual(config.model_name, "")
        self.assertEqual(config.name, "Demo Provider")

    def test_get_all_models_formats_multiple_provider_rows(self):
        raw_models = [
            {"id": 1, "provider_id": "provider-a", "model_name": "model-a"},
            {
                "id": 2,
                "provider_id": "provider-b",
                "model_name": "model-b",
                "created_at": "2026-06-01T00:00:00",
            },
        ]

        result = ModelService.get_all_models(
            all_models_lookup=Mock(return_value=raw_models),
            log=Mock(),
        )

        self.assertEqual(
            result,
            [
                {
                    "id": 1,
                    "provider_id": "provider-a",
                    "model_name": "model-a",
                    "created_at": None,
                },
                {
                    "id": 2,
                    "provider_id": "provider-b",
                    "model_name": "model-b",
                    "created_at": "2026-06-01T00:00:00",
                },
            ],
        )

    def test_add_new_model_skips_existing_model(self):
        insert_model = Mock()

        result = ModelService.add_new_model(
            "provider-1",
            "gpt-demo",
            provider_lookup=Mock(return_value={"id": "provider-1"}),
            existing_model_lookup=Mock(return_value={"id": 1}),
            insert_model_fn=insert_model,
            log=Mock(),
        )

        self.assertFalse(result)
        insert_model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
