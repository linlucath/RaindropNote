import logging
from collections.abc import Callable, Mapping
from typing import Any, Optional

from app.enmus.exception import ProviderErrorEnum
from app.exceptions.provider import ProviderError
from app.gpt.base import GPT
from app.gpt.gpt_factory import GPTFactory
from app.models.model_config import ModelConfig
from app.services.provider import ProviderService

logger = logging.getLogger(__name__)

ProviderLookup = Callable[[Optional[str]], Optional[Mapping[str, Any]]]


def build_gpt(
    model_name: Optional[str],
    provider_id: Optional[str],
    provider_lookup: Optional[ProviderLookup] = None,
    factory: Optional[GPTFactory] = None,
    log: logging.Logger = logger,
) -> GPT:
    """
    Build a GPT instance from a model name and saved provider configuration.
    """
    provider_lookup = provider_lookup or ProviderService.get_provider_by_id
    provider = provider_lookup(provider_id)
    if not provider:
        log.error(f"[get_gpt] 未找到模型供应商: provider_id={provider_id}")
        raise ProviderError(
            code=ProviderErrorEnum.NOT_FOUND,
            message=ProviderErrorEnum.NOT_FOUND.message,
        )

    log.info(f"创建 GPT 实例 {provider_id}")
    config = ModelConfig(
        api_key=provider["api_key"],
        base_url=provider["base_url"],
        model_name=model_name,
        provider=provider["type"],
        name=provider["name"],
    )
    gpt_factory = factory if factory is not None else GPTFactory()
    return gpt_factory.from_config(config)
