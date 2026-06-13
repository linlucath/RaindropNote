from __future__ import annotations

from pathlib import Path


def test_desktop_cors_origins_cover_tauri_runtime_hosts():
    repo_root = Path(__file__).parents[2]
    main_source = (repo_root / "backend" / "main.py").read_text(encoding="utf-8")

    for origin in [
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
        "https://localhost",
        "https://127.0.0.1",
    ]:
        assert origin in main_source
