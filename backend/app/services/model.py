
from app.db.model_dao import (
    delete_model as delete_model_record,
    get_all_models as get_all_model_records,
    get_model_by_provider_and_name,
    insert_model,
)
from app.enmus.exception import ProviderErrorEnum
from app.exceptions.provider import ProviderError
from app.gpt.gpt_factory import GPTFactory
from app.gpt.provider.OpenAI_compatible_provider import OpenAICompatibleProvider
from app.models.model_config import ModelConfig
from app.services.model_serialization import build_model_config, format_model_rows
from app.services.provider import ProviderService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ModelService:

    @staticmethod
    def _build_model_config(provider: dict) -> ModelConfig:
        return build_model_config(provider)

    @staticmethod
    def get_model_list(
        provider_id: int,
        verbose: bool = False,
        *,
        provider_lookup=None,
        factory=None,
        log=logger,
    ):
        provider_lookup = provider_lookup or ProviderService.get_provider_by_id
        provider = provider_lookup(provider_id)
        if not provider:
            return []

        try:
            config = ModelService._build_model_config(provider)
            gpt_factory = factory if factory is not None else GPTFactory()
            gpt = gpt_factory.from_config(config)
            models = gpt.list_models()
            if verbose:
                log.info(f"[{provider['name']}] 模型列表: {models}")
            return models
        except Exception as e:
            log.error(f"[{provider['name']}] 获取模型失败: {e}")
            return []

    @staticmethod
    def get_all_models(verbose: bool = False, *, all_models_lookup=None, log=logger):
        try:
            lookup = all_models_lookup or get_all_model_records
            raw_models = lookup()
            if verbose:
                log.info(f"所有模型列表: {raw_models}")
            return ModelService._format_models(raw_models)
        except Exception as e:
            log.error(f"获取所有模型失败: {e}")
            return []

    @staticmethod
    def get_all_models_safe(verbose: bool = False):
        return ModelService.get_all_models(verbose=verbose)

    @staticmethod
    def _format_models(raw_models: list) -> list:
        """
        格式化模型列表
        """
        return format_model_rows(raw_models)

    @staticmethod
    def get_enabled_models_by_provider(provider_id: str | int):
        from app.db.model_dao import get_models_by_provider

        all_models = get_models_by_provider(provider_id)
        enabled_models = all_models
        return enabled_models

    @staticmethod
    def get_all_models_by_id(provider_id: str, verbose: bool = False):
        try:
            provider = ProviderService.get_provider_by_id(provider_id)

            models = ModelService.get_model_list(provider["id"], verbose=verbose)
            serializable_models = [m.dict() for m in models.data]
            model_list = {
                "models": serializable_models
            }

            logger.info(f"[{provider['name']}] 获取模型成功")
            return model_list
        except Exception as e:
            logger.error(f"[{provider_id}] 获取模型失败: {e}")
            return []

    @staticmethod
    def connect_test(id: str) -> bool:

        provider = ProviderService.get_provider_by_id(id)

        if provider:
            if not provider.get('api_key'):
                raise ProviderError(code=ProviderErrorEnum.NOT_FOUND.code, message=ProviderErrorEnum.NOT_FOUND.message)
            result =  OpenAICompatibleProvider.test_connection(
                api_key=provider.get('api_key'),
                base_url=provider.get('base_url')
            )
            if result:
                return True
            else:
                raise ProviderError(code=ProviderErrorEnum.WRONG_PARAMETER.code,message=ProviderErrorEnum.WRONG_PARAMETER.message)

        raise ProviderError(code=ProviderErrorEnum.NOT_FOUND.code, message=ProviderErrorEnum.NOT_FOUND.message)

    @staticmethod
    def delete_model_by_id(model_id: int, *, delete_model_fn=None, log=logger) -> bool:
        try:
            delete_fn = delete_model_fn or delete_model_record
            delete_fn(model_id)
            return True
        except Exception as e:
            log.error(f"[{model_id}] 删除模型失败: {e}")
            return False

    @staticmethod
    def add_new_model(
        provider_id: int,
        model_name: str,
        *,
        provider_lookup=None,
        existing_model_lookup=None,
        insert_model_fn=None,
        log=logger,
    ) -> bool:
        try:
            provider_lookup = provider_lookup or ProviderService.get_provider_by_id
            existing_model_lookup = existing_model_lookup or get_model_by_provider_and_name
            insert_model_fn = insert_model_fn or insert_model

            # 先查供应商是否存在
            provider = provider_lookup(provider_id)
            if not provider:
                log.warning(f"供应商ID {provider_id} 不存在，无法添加模型")
                return False

            # 查询是否已存在同名模型
            existing = existing_model_lookup(provider_id, model_name)
            if existing:
                log.info(f"模型 {model_name} 已存在于供应商ID {provider_id} 下，跳过插入")
                return False

            # 插入模型
            insert_model_fn(provider_id=provider_id, model_name=model_name)
            log.info(f"模型 {model_name} 已成功添加到供应商ID {provider_id}")
            return True
        except Exception as e:
            log.error(f"添加模型失败: {e}")
            return False


if __name__ == '__main__':
    # 单个 Provider 测试
    logger.info(ModelService.get_model_list(1, verbose=True))
