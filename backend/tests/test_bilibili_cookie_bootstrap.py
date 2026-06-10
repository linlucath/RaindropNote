from types import SimpleNamespace

from app.services.bilibili_cookie_bootstrap import (
    BilibiliCookieBootstrapService,
    discovery_browser_order,
    schedule_cookie_bootstrap,
)


def test_discovery_browser_order_is_os_specific():
    assert discovery_browser_order('Windows') == ['edge', 'chrome', 'chromium', 'brave']
    assert discovery_browser_order('Darwin') == ['edge', 'chrome', 'chromium', 'brave', 'safari']


def test_bootstrap_skips_when_cookie_already_exists():
    calls = []
    cookie_manager = SimpleNamespace(
        get=lambda platform: 'SESSDATA=configured' if platform == 'bilibili' else '',
        set=lambda platform, cookie: calls.append((platform, cookie)),
    )
    service = BilibiliCookieBootstrapService(
        cookie_manager=cookie_manager,
        browser_reader=lambda _browser: (_ for _ in ()).throw(AssertionError('should not read browser')),
        validator=lambda cookie: cookie,
    )

    assert service.bootstrap() is None
    assert calls == []


def test_bootstrap_saves_first_valid_cookie_and_stops():
    saved = []
    attempted = []
    cookie_manager = SimpleNamespace(
        get=lambda _platform: '',
        set=lambda platform, cookie: saved.append((platform, cookie)),
    )

    def browser_reader(browser):
        attempted.append(browser)
        if browser == 'edge':
            return []
        if browser == 'chrome':
            return [
                SimpleNamespace(domain='.bilibili.com', name='SESSDATA', value='test'),
                SimpleNamespace(domain='.bilibili.com', name='DedeUserID', value='12345'),
            ]
        raise AssertionError('should stop after first valid browser')

    service = BilibiliCookieBootstrapService(
        cookie_manager=cookie_manager,
        browser_reader=browser_reader,
        validator=lambda cookie: cookie,
        system_name='Windows',
    )

    cookie = service.bootstrap()

    assert cookie == 'SESSDATA=test; DedeUserID=12345'
    assert attempted == ['edge', 'chrome']
    assert saved == [('bilibili', 'SESSDATA=test; DedeUserID=12345')]


def test_bootstrap_ignores_browser_and_validation_failures():
    saved = []
    attempted = []
    cookie_manager = SimpleNamespace(
        get=lambda _platform: '',
        set=lambda platform, cookie: saved.append((platform, cookie)),
    )

    def browser_reader(browser):
        attempted.append(browser)
        if browser == 'edge':
            raise RuntimeError('locked db')
        if browser == 'chrome':
            return [
                SimpleNamespace(domain='.bilibili.com', name='SESSDATA', value='bad'),
                SimpleNamespace(domain='.bilibili.com', name='DedeUserID', value='12345'),
            ]
        if browser == 'chromium':
            return [
                SimpleNamespace(domain='.bilibili.com', name='SESSDATA', value='good'),
                SimpleNamespace(domain='.bilibili.com', name='DedeUserID', value='12345'),
            ]
        return []

    def validator(cookie):
        if 'SESSDATA=bad' in cookie:
            raise ValueError('invalid cookie')
        return cookie

    service = BilibiliCookieBootstrapService(
        cookie_manager=cookie_manager,
        browser_reader=browser_reader,
        validator=validator,
        system_name='Windows',
    )

    cookie = service.bootstrap()

    assert cookie == 'SESSDATA=good; DedeUserID=12345'
    assert attempted == ['edge', 'chrome', 'chromium']
    assert saved == [('bilibili', 'SESSDATA=good; DedeUserID=12345')]


def test_schedule_cookie_bootstrap_skips_when_cookie_exists():
    started = []
    cookie_manager = SimpleNamespace(get=lambda _platform: 'SESSDATA=configured')

    schedule_cookie_bootstrap(
        cookie_manager=cookie_manager,
        bootstrap_runner=lambda: started.append('ran'),
        thread_factory=lambda **kwargs: SimpleNamespace(start=lambda: started.append(kwargs)),
    )

    assert started == []


def test_schedule_cookie_bootstrap_starts_background_thread():
    started = []
    thread_kwargs = {}
    cookie_manager = SimpleNamespace(get=lambda _platform: '')

    def thread_factory(**kwargs):
        thread_kwargs.update(kwargs)
        return SimpleNamespace(start=lambda: started.append('started'))

    schedule_cookie_bootstrap(
        cookie_manager=cookie_manager,
        bootstrap_runner=lambda: started.append('ran'),
        thread_factory=thread_factory,
    )

    assert started == ['started']
    assert thread_kwargs['daemon'] is True
    assert callable(thread_kwargs['target'])
