import os
from pathlib import Path

from app.utils.path_helper import get_uploads_dir


def resolve_local_video_path(video_url: str, *, project_root: str | None = None) -> str:
    if not video_url.startswith('/uploads'):
        return video_url

    relative_path = video_url.removeprefix("/uploads").lstrip("/")
    uploads_dir = Path(project_root) / "uploads" if project_root is not None else Path(get_uploads_dir())
    return os.path.normpath(os.fspath(uploads_dir / relative_path))
