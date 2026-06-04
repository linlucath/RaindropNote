from collections.abc import Iterator, Mapping
from importlib import import_module
from threading import RLock
from typing import Any, NamedTuple


class DownloaderSpec(NamedTuple):
    module: str
    class_name: str


class LazyDownloaderMap(Mapping[str, Any]):
    def __init__(self, specs: Mapping[str, DownloaderSpec]):
        self._specs = dict(specs)
        self._instances: dict[str, Any] = {}
        self._lock = RLock()

    def __getitem__(self, key: str) -> Any:
        if key not in self._specs:
            raise KeyError(key)

        with self._lock:
            if key not in self._instances:
                spec = self._specs[key]
                module = import_module(spec.module)
                downloader_cls = getattr(module, spec.class_name)
                self._instances[key] = downloader_cls()
            return self._instances[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._specs)

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, key: object) -> bool:
        return key in self._specs

    def copy(self) -> dict[str, Any]:
        return {key: self[key] for key in self._specs}


SUPPORT_PLATFORM_MAP = LazyDownloaderMap(
    {
        'youtube': DownloaderSpec(
            'app.downloaders.youtube_downloader',
            'YoutubeDownloader',
        ),
        'bilibili': DownloaderSpec(
            'app.downloaders.bilibili_downloader',
            'BilibiliDownloader',
        ),
        'tiktok': DownloaderSpec(
            'app.downloaders.douyin_downloader',
            'DouyinDownloader',
        ),
        'kuaishou': DownloaderSpec(
            'app.downloaders.kuaishou_downloader',
            'KuaiShouDownloader',
        ),
        'douyin': DownloaderSpec(
            'app.downloaders.douyin_downloader',
            'DouyinDownloader',
        ),
    }
)
