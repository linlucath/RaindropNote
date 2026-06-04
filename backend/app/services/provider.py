from kombu import uuid

from app.db.models.providers import Provider
from app.db.provider_dao import (
    delete_provider as delete_provider_record,
    get_all_providers as get_all_provider_records,
    get_provider_by_id as get_provider_record_by_id,
    get_provider_by_name as get_provider_record_by_name,
    insert_provider,
    update_provider as update_provider_record,
)
from app.services.provider_serialization import (
    mask_api_key,
    provider_to_dict,
    serialize_provider as serialize_provider_row,
)
from app.utils.logger import get_logger


logger = get_logger(__name__)


class ProviderService:

    @staticmethod
    def serialize_provider(row: Provider) -> dict:
        return serialize_provider_row(row)

    @staticmethod
    def serialize_provider_safe(row: Provider) -> dict:
        return serialize_provider_row(row, mask_key=True)

    @staticmethod
    def mask_key(key: str) -> str:
        return mask_api_key(key)

    @staticmethod
    def add_provider(
        name: str,
        api_key: str,
        base_url: str,
        logo: str,
        type_: str,
        enabled: int = 1,
        *,
        id_factory=None,
        insert_provider_fn=None,
        log=logger,
    ):
        try:
            id_factory = id_factory or uuid
            insert_provider_fn = insert_provider_fn or insert_provider
            provider_id = str(id_factory()).lower()
            logo = 'custom'
            return insert_provider_fn(provider_id, name, api_key, base_url, logo, type_, enabled)
        except Exception as e:
            log.error(f'创建模型供应商失败: {e}')
            return None

    @staticmethod
    def provider_to_dict(p: Provider):
        return provider_to_dict(p)

    @staticmethod
    def get_all_providers(*, providers_lookup=None):
        providers_lookup = providers_lookup or get_all_provider_records
        rows = providers_lookup()
        if rows is None:
            return []

        return [ProviderService.serialize_provider(row) for row in rows] if rows else []

    @staticmethod
    def get_all_providers_safe(*, providers_lookup=None):
        providers_lookup = providers_lookup or get_all_provider_records
        rows = providers_lookup()

        return [ProviderService.serialize_provider(row) for row in rows] if (rows) else []

    @staticmethod
    def get_provider_by_name(name: str, *, provider_lookup=None):
        provider_lookup = provider_lookup or get_provider_record_by_name
        row = provider_lookup(name)
        return ProviderService.serialize_provider(row)

    @staticmethod
    def get_provider_by_id(id: str, *, provider_lookup=None):
        provider_lookup = provider_lookup or get_provider_record_by_id
        row = provider_lookup(id)
        return ProviderService.serialize_provider(row)

    @staticmethod
    def get_provider_by_id_safe(id: str, *, provider_lookup=None):
        provider_lookup = provider_lookup or get_provider_record_by_id
        row = provider_lookup(id)
        return ProviderService.serialize_provider_safe(row)

    @staticmethod
    def update_provider(
        id: str,
        data: dict,
        *,
        update_provider_fn=None,
        log=logger,
    ) -> str | None:
        try:
            update_provider_fn = update_provider_fn or update_provider_record
            filtered_data = {k: v for k, v in data.items() if v is not None and k != 'id'}
            log.info(f'更新模型供应商: {filtered_data}')
            update_provider_fn(id, **filtered_data)
            return id

        except Exception as e:
            log.error(f'更新模型供应商失败: {e}')
            return None

    @staticmethod
    def delete_provider(id: str, *, delete_provider_fn=None):
        delete_provider_fn = delete_provider_fn or delete_provider_record
        return delete_provider_fn(id)
