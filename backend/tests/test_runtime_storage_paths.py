from __future__ import annotations

from pathlib import Path

from app.downloaders import local_paths
from app.utils import path_helper


def test_runtime_static_and_upload_dirs_use_app_data_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(path_helper, "get_app_dir", lambda subdir="": str(tmp_path / subdir))

    assert Path(path_helper.get_static_dir()) == tmp_path / "static"
    assert Path(path_helper.get_uploads_dir()) == tmp_path / "uploads"


def test_runtime_screenshot_dir_defaults_under_runtime_static_dir(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("OUT_DIR", raising=False)
    monkeypatch.setattr(path_helper, "get_app_dir", lambda subdir="": str(tmp_path / subdir))

    assert Path(path_helper.get_screenshot_dir()) == tmp_path / "static" / "screenshots"


def test_runtime_screenshot_dir_resolves_relative_env_under_app_data_dir(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("OUT_DIR", "./static/screenshots")
    monkeypatch.setattr(path_helper, "get_app_dir", lambda subdir="": str(tmp_path / subdir))

    assert Path(path_helper.get_screenshot_dir()) == tmp_path / "static" / "screenshots"


def test_runtime_screenshot_dir_preserves_absolute_env(monkeypatch, tmp_path: Path):
    screenshot_dir = tmp_path / "custom-screenshots"
    monkeypatch.setenv("OUT_DIR", str(screenshot_dir))

    assert Path(path_helper.get_screenshot_dir()) == screenshot_dir


def test_uploaded_local_video_urls_resolve_under_runtime_upload_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(local_paths, "get_uploads_dir", lambda: str(tmp_path / "uploads"))

    assert (
        resolve := local_paths.resolve_local_video_path("/uploads/demo/video.mp4")
    ) == str(tmp_path / "uploads" / "demo" / "video.mp4")
    assert "/uploads/uploads/" not in resolve


def test_main_uses_runtime_storage_helpers():
    repo_root = Path(__file__).parents[2]
    main_source = (repo_root / "backend" / "main.py").read_text(encoding="utf-8")

    assert "get_static_dir" in main_source
    assert "get_uploads_dir" in main_source
    assert "get_screenshot_dir" in main_source
    assert 'static_dir = "static"' not in main_source
    assert 'uploads_dir = "uploads"' not in main_source
    assert 'os.getenv(\'OUT_DIR\', \'./static/screenshots\')' not in main_source


def test_frozen_macos_app_dir_uses_application_support(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(path_helper, "Path", Path)
    monkeypatch.setattr(path_helper, "sys", type("FrozenSys", (), {"frozen": True, "platform": "darwin"})())
    monkeypatch.setattr(path_helper.Path, "home", lambda: tmp_path)
    monkeypatch.delenv("RAINDROPNOTE_APP_DIR", raising=False)

    assert Path(path_helper.get_app_dir()) == tmp_path / "Library" / "Application Support" / "RaindropNote"


def test_runtime_override_app_dir_wins_in_frozen_mode(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(path_helper, "sys", type("FrozenSys", (), {"frozen": True, "platform": "darwin"})())
    override_dir = tmp_path / "portable-data"
    monkeypatch.setenv("RAINDROPNOTE_APP_DIR", str(override_dir))

    assert Path(path_helper.get_app_dir("logs")) == override_dir / "logs"
