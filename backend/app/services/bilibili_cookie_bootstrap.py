from __future__ import annotations

import logging
import platform
import threading
from collections.abc import Callable, Iterable
from typing import Any

logger = logging.getLogger(__name__)


def discovery_browser_order(system_name: str | None = None) -> list[str]:
    active_system = system_name or platform.system()
    if active_system == 'Windows':
        return ['edge', 'chrome', 'chromium', 'brave']
    if active_system == 'Darwin':
        return ['edge', 'chrome', 'chromium', 'brave', 'safari']
    return ['chrome', 'chromium', 'brave']


def _default_browser_reader(browser: str) -> Iterable[Any]:
    import browser_cookie3

    reader = getattr(browser_cookie3, browser)
    return reader(domain_name='bilibili.com')


def _build_cookie_string(cookies: Iterable[Any]) -> str:
    parts: list[str] = []
    for cookie in cookies:
        domain = str(getattr(cookie, 'domain', '') or '')
        if 'bilibili.com' not in domain:
            continue
        name = str(getattr(cookie, 'name', '') or '').strip()
        value = str(getattr(cookie, 'value', '') or '').strip()
        if not name:
            continue
        parts.append(f'{name}={value}')
    return '; '.join(parts)


class BilibiliCookieBootstrapService:
    def __init__(
        self,
        *,
        cookie_manager,
        validator: Callable[[str], str],
        browser_reader: Callable[[str], Iterable[Any]] | None = None,
        system_name: str | None = None,
        request_logger: logging.Logger | None = None,
    ):
        self.cookie_manager = cookie_manager
        self.validator = validator
        self.browser_reader = browser_reader or _default_browser_reader
        self.system_name = system_name
        self.logger = request_logger or logger

    def bootstrap(self) -> str | None:
        if (self.cookie_manager.get('bilibili') or '').strip():
            self.logger.info('Skip Bilibili cookie bootstrap because cookie already exists')
            return None

        for browser in discovery_browser_order(self.system_name):
            try:
                cookies = self.browser_reader(browser)
                candidate = _build_cookie_string(cookies)
                if not candidate:
                    continue
                validated = self.validator(candidate)
                self.cookie_manager.set('bilibili', validated)
                self.logger.info('Bootstrapped Bilibili cookie from browser: %s', browser)
                return validated
            except Exception as exc:
                self.logger.info('Bilibili cookie bootstrap failed for browser %s: %s', browser, exc)

        return None


def schedule_cookie_bootstrap(
    *,
    cookie_manager,
    bootstrap_runner: Callable[[], Any],
    thread_factory: Callable[..., Any] = threading.Thread,
) -> None:
    if (cookie_manager.get('bilibili') or '').strip():
        return

    thread = thread_factory(target=bootstrap_runner, daemon=True, name='bilibili-cookie-bootstrap')
    thread.start()
