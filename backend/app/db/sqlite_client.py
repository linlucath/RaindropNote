import sqlite3
from pathlib import Path

from app.utils.path_helper import get_app_dir


def get_connection():
    database_path = Path(get_app_dir()) / "raindrop_note.db"
    return sqlite3.connect(database_path)
