import subprocess
import sys
import textwrap


def test_note_tasks_import_does_not_import_note_generator_module():
    code = textwrap.dedent(
        """
        import sys

        import app.services.note_tasks  # noqa: F401

        assert "app.services.note" not in sys.modules
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
