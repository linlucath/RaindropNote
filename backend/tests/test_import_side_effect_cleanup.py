import importlib
import sys
from types import SimpleNamespace
from unittest.mock import patch

from app.decorators.timeit import timeit


def test_importing_xiaoyuzhoufm_download_does_not_request_network_or_print_stdout(capsys):
    module_name = "app.downloaders.xiaoyuzhoufm_download"
    original_module = sys.modules.pop(module_name, None)

    fake_response = SimpleNamespace(json=lambda: {"ok": True})

    try:
        with patch("requests.get", return_value=fake_response) as get:
            importlib.import_module(module_name)
    finally:
        if original_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original_module

    assert get.call_count == 0
    assert capsys.readouterr().out == ""


def test_timeit_does_not_write_timing_to_stdout(capsys):
    @timeit
    def add(left, right):
        return left + right

    result = add(1, 2)

    assert result == 3
    assert capsys.readouterr().out == ""
