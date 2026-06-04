import importlib
import sys
import types

import pytest


DOWNLOADER_MODULES = {
    "app.downloaders.bilibili_downloader": "BilibiliDownloader",
    "app.downloaders.douyin_downloader": "DouyinDownloader",
    "app.downloaders.kuaishou_downloader": "KuaiShouDownloader",
    "app.downloaders.youtube_downloader": "YoutubeDownloader",
}


@pytest.fixture
def isolated_downloader_modules(monkeypatch):
    calls = []
    classes = {}

    def make_downloader(class_name):
        class FakeDownloader:
            def __init__(self):
                calls.append(class_name)

        FakeDownloader.__name__ = class_name
        return FakeDownloader

    for module_name, class_name in DOWNLOADER_MODULES.items():
        module = types.ModuleType(module_name)

        FakeDownloader = make_downloader(class_name)
        FakeDownloader.__module__ = module_name
        setattr(module, class_name, FakeDownloader)
        classes[class_name] = FakeDownloader
        monkeypatch.setitem(sys.modules, module_name, module)

    sys.modules.pop("app.services.constant", None)
    yield calls, classes
    sys.modules.pop("app.services.constant", None)


def test_importing_registry_does_not_instantiate_downloaders(isolated_downloader_modules):
    calls, _ = isolated_downloader_modules

    importlib.import_module("app.services.constant")

    assert calls == []


def test_support_platform_map_lazily_returns_downloader_instances(isolated_downloader_modules):
    calls, classes = isolated_downloader_modules
    constant = importlib.import_module("app.services.constant")

    registry = constant.SUPPORT_PLATFORM_MAP

    assert list(registry.keys()) == ["youtube", "bilibili", "tiktok", "kuaishou", "douyin"]
    assert list(registry) == ["youtube", "bilibili", "tiktok", "kuaishou", "douyin"]
    assert "bilibili" in registry
    assert "unsupported" not in registry
    assert registry.get("unsupported") is None
    assert registry.get("unsupported", "fallback") == "fallback"
    assert calls == []

    assert isinstance(registry["bilibili"], classes["BilibiliDownloader"])
    assert isinstance(registry.get("douyin"), classes["DouyinDownloader"])
    assert isinstance(registry["tiktok"], classes["DouyinDownloader"])
    assert isinstance(registry["youtube"], classes["YoutubeDownloader"])
    assert isinstance(registry["kuaishou"], classes["KuaiShouDownloader"])

    assert calls == [
        "BilibiliDownloader",
        "DouyinDownloader",
        "DouyinDownloader",
        "YoutubeDownloader",
        "KuaiShouDownloader",
    ]
    assert registry["bilibili"] is registry["bilibili"]

    with pytest.raises(KeyError):
        registry["unsupported"]


def test_support_platform_map_copy_keeps_legacy_dict_behavior(isolated_downloader_modules):
    calls, classes = isolated_downloader_modules
    constant = importlib.import_module("app.services.constant")

    copied = constant.SUPPORT_PLATFORM_MAP.copy()

    assert isinstance(copied, dict)
    assert list(copied.keys()) == ["youtube", "bilibili", "tiktok", "kuaishou", "douyin"]
    assert isinstance(copied["youtube"], classes["YoutubeDownloader"])
    assert isinstance(copied["bilibili"], classes["BilibiliDownloader"])
    assert isinstance(copied["tiktok"], classes["DouyinDownloader"])
    assert isinstance(copied["kuaishou"], classes["KuaiShouDownloader"])
    assert isinstance(copied["douyin"], classes["DouyinDownloader"])
    assert calls == [
        "YoutubeDownloader",
        "BilibiliDownloader",
        "DouyinDownloader",
        "KuaiShouDownloader",
        "DouyinDownloader",
    ]
