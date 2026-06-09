import importlib
import os
import subprocess
import sys
import textwrap
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


def test_importing_note_service_does_not_create_note_output_dir(tmp_path):
    output_dir = tmp_path / "notes"
    code = textwrap.dedent(
        f"""
        import os

        os.environ["NOTE_OUTPUT_DIR"] = {str(output_dir)!r}

        import app.services.note  # noqa: F401

        assert not os.path.exists({str(output_dir)!r})
        """
    )

    env = os.environ.copy()
    env["NOTE_OUTPUT_DIR"] = str(output_dir)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr


def test_importing_note_service_does_not_load_dotenv():
    code = textwrap.dedent(
        """
        import dotenv

        calls = []

        def fake_load_dotenv(*args, **kwargs):
            calls.append((args, kwargs))

        dotenv.load_dotenv = fake_load_dotenv

        import app.services.note  # noqa: F401

        assert calls == []
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_importing_batch_state_does_not_create_batch_output_dir(tmp_path):
    note_output_dir = tmp_path / "notes"
    batch_output_dir = note_output_dir / "batches"
    code = textwrap.dedent(
        f"""
        import os

        os.environ["NOTE_OUTPUT_DIR"] = {str(note_output_dir)!r}

        import app.services.batch_state  # noqa: F401

        assert not os.path.exists({str(batch_output_dir)!r})
        """
    )

    env = os.environ.copy()
    env["NOTE_OUTPUT_DIR"] = str(note_output_dir)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
