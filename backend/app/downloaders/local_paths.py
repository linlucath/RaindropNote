import os


def resolve_local_video_path(video_url: str, *, project_root: str | None = None) -> str:
    if not video_url.startswith('/uploads'):
        return video_url

    root = project_root if project_root is not None else os.getcwd()
    return os.path.normpath(os.path.join(root, video_url.lstrip('/')))
