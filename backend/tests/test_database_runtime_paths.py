from __future__ import annotations

from pathlib import Path

from app.db import engine
from app.db import sqlite_client


def test_default_database_url_uses_app_data_dir(monkeypatch, tmp_path: Path):
    database_path = tmp_path / "raindrop_note.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(engine, "get_app_dir", lambda filename="": str(tmp_path / filename))

    assert engine.resolve_database_url() == f"sqlite:///{database_path}"


def test_explicit_database_url_is_preserved(monkeypatch):
    database_url = "postgresql://user:pass@example.com:5432/raindrop"
    monkeypatch.setenv("DATABASE_URL", database_url)

    assert engine.resolve_database_url() == database_url


def test_sqlite_client_uses_app_data_database_path(monkeypatch, tmp_path: Path):
    captured_paths = []

    def fake_connect(path):
        captured_paths.append(path)
        return object()

    monkeypatch.setattr(sqlite_client, "get_app_dir", lambda: str(tmp_path))
    monkeypatch.setattr(sqlite_client.sqlite3, "connect", fake_connect)

    assert sqlite_client.get_connection() is not None
    assert captured_paths == [tmp_path / "raindrop_note.db"]
