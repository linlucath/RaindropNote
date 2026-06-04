import json

from app.routers import model as model_router
from app.routers import provider as provider_router


def _json_body(response):
    return json.loads(response.body.decode("utf-8"))


def _endpoint(path: str):
    for route in model_router.router.routes:
        if getattr(route, "path", None) == path:
            return route.endpoint
    raise AssertionError(f"Route not found: {path}")


def test_update_provider_exception_does_not_print_stdout(monkeypatch, capsys):
    def raise_error(**_kwargs):
        raise RuntimeError("provider update exploded")

    monkeypatch.setattr(provider_router.ProviderService, "update_provider", raise_error)

    response = provider_router.update_provider(
        provider_router.ProviderUpdateRequest(
            id="provider-1",
            name="Demo Provider",
        )
    )

    assert capsys.readouterr().out == ""
    body = _json_body(response)
    assert body["code"] == 500
    assert "provider update exploded" in body["msg"]


def test_model_list_uses_runtime_model_service(monkeypatch):
    created_services = []

    class RuntimeModelService:
        def __init__(self):
            created_services.append(self)

        def get_all_models(self, verbose=False):
            return [{"id": 1, "model_name": "runtime-model", "verbose": verbose}]

    monkeypatch.setattr(model_router, "ModelService", RuntimeModelService)

    response = _endpoint("/model_list")()

    assert len(created_services) == 1
    body = _json_body(response)
    assert body["code"] == 0
    assert body["msg"] == "获取模型列表成功"
    assert body["data"] == [{"id": 1, "model_name": "runtime-model", "verbose": True}]


def test_model_list_keeps_legacy_model_service_patchable(monkeypatch):
    class LegacyModelService:
        def __init__(self):
            self.called = False

        def get_all_models(self, verbose=False):
            self.called = True
            return [{"id": 9, "model_name": "legacy-service", "verbose": verbose}]

    legacy_service = LegacyModelService()
    monkeypatch.setattr(model_router, "modelService", legacy_service)

    response = _endpoint("/model_list")()

    assert legacy_service.called
    body = _json_body(response)
    assert body["code"] == 0
    assert body["data"] == [{"id": 9, "model_name": "legacy-service", "verbose": True}]


def test_delete_model_uses_runtime_model_service(monkeypatch):
    created_services = []

    class RuntimeModelService:
        def __init__(self):
            created_services.append(self)

        def delete_model_by_id(self, model_id):
            self.model_id = model_id
            return True

    monkeypatch.setattr(model_router, "ModelService", RuntimeModelService)

    response = model_router.delete_model(42)

    assert len(created_services) == 1
    assert created_services[0].model_id == 42
    body = _json_body(response)
    assert body["code"] == 0
    assert body["msg"] == "模型删除成功"


def test_get_enabled_models_by_provider_uses_runtime_model_service(monkeypatch):
    created_services = []

    class RuntimeModelService:
        def __init__(self):
            created_services.append(self)

        def get_enabled_models_by_provider(self, provider_id):
            self.provider_id = provider_id
            return [{"id": 2, "model_name": "enabled-runtime-model"}]

    monkeypatch.setattr(model_router, "ModelService", RuntimeModelService)

    response = model_router.get_enabled_models_by_provider("provider-2")

    assert len(created_services) == 1
    assert created_services[0].provider_id == "provider-2"
    body = _json_body(response)
    assert body["code"] == 0
    assert body["msg"] == "获取启用模型成功"
    assert body["data"] == [{"id": 2, "model_name": "enabled-runtime-model"}]
