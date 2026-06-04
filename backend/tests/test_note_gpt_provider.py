import unittest
from unittest.mock import Mock, patch

from app.enmus.exception import ProviderErrorEnum
from app.exceptions.provider import ProviderError
from app.models.model_config import ModelConfig
from app.services.note_gpt_provider import build_gpt


class TestNoteGptProvider(unittest.TestCase):
    def test_build_gpt_creates_model_config_from_provider(self):
        provider_lookup = Mock(
            return_value={
                "id": "provider-1",
                "name": "Demo Provider",
                "type": "openai",
                "api_key": "sk-demo",
                "base_url": "https://api.example.test/v1",
            }
        )
        gpt = object()
        factory = Mock()
        factory.from_config.return_value = gpt
        log = Mock()

        result = build_gpt(
            "gpt-demo",
            "provider-1",
            provider_lookup=provider_lookup,
            factory=factory,
            log=log,
        )

        self.assertIs(result, gpt)
        provider_lookup.assert_called_once_with("provider-1")
        factory.from_config.assert_called_once()
        config = factory.from_config.call_args.args[0]
        self.assertIsInstance(config, ModelConfig)
        self.assertEqual(config.api_key, "sk-demo")
        self.assertEqual(config.base_url, "https://api.example.test/v1")
        self.assertEqual(config.model_name, "gpt-demo")
        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.name, "Demo Provider")
        log.info.assert_called_once_with("创建 GPT 实例 provider-1")

    def test_build_gpt_raises_provider_error_when_provider_missing(self):
        provider_lookup = Mock(return_value=None)
        factory = Mock()
        log = Mock()

        with self.assertRaises(ProviderError) as ctx:
            build_gpt(
                "gpt-demo",
                "missing-provider",
                provider_lookup=provider_lookup,
                factory=factory,
                log=log,
            )

        self.assertEqual(ctx.exception.code, ProviderErrorEnum.NOT_FOUND)
        self.assertEqual(ctx.exception.message, ProviderErrorEnum.NOT_FOUND.message)
        provider_lookup.assert_called_once_with("missing-provider")
        factory.from_config.assert_not_called()
        log.error.assert_called_once_with(
            "[get_gpt] 未找到模型供应商: provider_id=missing-provider"
        )

    def test_build_gpt_uses_runtime_provider_service_patch_by_default(self):
        patched_lookup = Mock(
            return_value={
                "id": "provider-1",
                "name": "Patched Provider",
                "type": "openai",
                "api_key": "sk-patched",
                "base_url": "https://patched.example.test/v1",
            }
        )
        gpt = object()
        factory = Mock()
        factory.from_config.return_value = gpt

        with patch(
            "app.services.note_gpt_provider.ProviderService.get_provider_by_id",
            patched_lookup,
        ):
            result = build_gpt("gpt-demo", "provider-1", factory=factory, log=Mock())

        self.assertIs(result, gpt)
        patched_lookup.assert_called_once_with("provider-1")


if __name__ == "__main__":
    unittest.main()
