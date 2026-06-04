import os
from pathlib import Path

from app.enmus.task_status_enums import TaskStatus


SUPPORTED_GENERATION_MODE = "polished_transcript"

ACTIVE_TASK_STATUSES = {
    TaskStatus.PENDING.value,
    TaskStatus.PARSING.value,
    TaskStatus.DOWNLOADING.value,
    TaskStatus.TRANSCRIBING.value,
    TaskStatus.SUMMARIZING.value,
    TaskStatus.FORMATTING.value,
    TaskStatus.SAVING.value,
    TaskStatus.CANCELLING.value,
}
ACTIVE_BATCH_STATUSES = {
    TaskStatus.PENDING.value,
    "RUNNING",
    TaskStatus.CANCELLING.value,
}
TERMINAL_TASK_STATUSES = {
    TaskStatus.SUCCESS.value,
    TaskStatus.FAILED.value,
    TaskStatus.CANCELLED.value,
}
TERMINAL_BATCH_STATUSES = set(TERMINAL_TASK_STATUSES)
COMPLETED_ITEM_STATUSES = {
    TaskStatus.SUCCESS.value,
    TaskStatus.FAILED.value,
    "SKIPPED",
    TaskStatus.CANCELLED.value,
}


def default_note_output_dir() -> Path:
    return Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))


def default_batch_output_dir(note_output_dir: Path | str | None = None) -> Path:
    if note_output_dir is None:
        note_output_dir = default_note_output_dir()
    return Path(note_output_dir) / "batches"
