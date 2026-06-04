import json
from datetime import datetime, timezone


def test_checkpoint_path_sanitizes_key_and_uses_legacy_suffix(tmp_path):
    from app.gpt.checkpoint_store import checkpoint_path

    path = checkpoint_path(tmp_path, "task/id:with spaces")

    assert path == tmp_path / "task_id_with_spaces.gpt.checkpoint.json"


def test_save_and_load_checkpoint_round_trip(tmp_path):
    from app.gpt.checkpoint_store import load_checkpoint, save_checkpoint

    updated_at = datetime(2026, 6, 2, 8, 30, tzinfo=timezone.utc)

    save_checkpoint(
        tmp_path,
        "task-1",
        "sig-1",
        ["part-a", "part-b"],
        "summarize",
        updated_at=updated_at,
    )

    data = load_checkpoint(tmp_path, "task-1", "sig-1")

    assert data == {
        "version": 1,
        "source_signature": "sig-1",
        "phase": "summarize",
        "partials": ["part-a", "part-b"],
        "updated_at": "2026-06-02T08:30:00+00:00",
    }


def test_load_checkpoint_deletes_and_ignores_source_signature_mismatch(tmp_path):
    from app.gpt.checkpoint_store import checkpoint_path, load_checkpoint, save_checkpoint

    save_checkpoint(tmp_path, "task-1", "sig-old", ["stale"], "merge")
    path = checkpoint_path(tmp_path, "task-1")

    assert load_checkpoint(tmp_path, "task-1", "sig-new") is None
    assert not path.exists()


def test_load_checkpoint_deletes_and_ignores_invalid_json(tmp_path):
    from app.gpt.checkpoint_store import checkpoint_path, load_checkpoint

    path = checkpoint_path(tmp_path, "task-1")
    path.write_text("{not json", encoding="utf-8")

    assert load_checkpoint(tmp_path, "task-1", "sig-1") is None
    assert not path.exists()


def test_save_checkpoint_replaces_existing_payload_atomically(tmp_path):
    from app.gpt.checkpoint_store import checkpoint_path, save_checkpoint

    path = checkpoint_path(tmp_path, "task-1")
    path.write_text(json.dumps({"old": True}), encoding="utf-8")

    save_checkpoint(tmp_path, "task-1", "sig-1", ["new"], "merge")

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["source_signature"] == "sig-1"
    assert data["partials"] == ["new"]
    assert data["phase"] == "merge"
    assert "old" not in data
