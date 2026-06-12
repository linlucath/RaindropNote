import os
import sys
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
APP_NAME = "RaindropNote"


def _runtime_base_dir() -> Path:
    override = os.getenv("RAINDROPNOTE_APP_DIR")
    if override:
        base_dir = Path(override).expanduser()
    elif getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            base_dir = Path.home() / "Library" / "Application Support" / APP_NAME
        elif sys.platform == "win32":
            appdata_root = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
            base_dir = appdata_root / APP_NAME
        else:
            data_home = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
            base_dir = data_home / APP_NAME
    else:
        base_dir = Path(__file__).resolve().parents[2] / "data"

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_data_dir():
    data_path = _runtime_base_dir() / "data"
    data_path.mkdir(parents=True, exist_ok=True)
    return str(data_path)


def get_model_dir(subdir: str = "whisper") -> str:
    # 判断是否为打包状态（PyInstaller）
    if getattr(sys, 'frozen', False):
        # exe 执行，放在 APPDATA 或 ~/.cache 下
        base_dir = os.path.join(os.getenv("APPDATA") or str(Path.home()), "RaindropNote", "models")
    else:
        # 开发时，相对项目根目录
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../models"))

    path = os.path.join(base_dir, subdir)
    os.makedirs(path, exist_ok=True)
    return path


def get_app_dir(subdir: str = "") -> str:
    """
    返回一个稳定的可写目录：
    - 开发时：使用项目 data 目录
    - 打包后：使用用户应用数据目录
    """
    full_path = _runtime_base_dir() / subdir if subdir else _runtime_base_dir()
    full_path.mkdir(parents=True, exist_ok=True)
    return str(full_path)


def get_static_dir() -> str:
    return get_app_dir("static")


def get_uploads_dir() -> str:
    return get_app_dir("uploads")


def get_screenshot_dir() -> str:
    configured_dir = os.getenv("OUT_DIR")
    if configured_dir:
        screenshot_path = Path(configured_dir)
        if not screenshot_path.is_absolute():
            screenshot_path = Path(get_app_dir()) / screenshot_path
    else:
        screenshot_path = Path(get_static_dir()) / "screenshots"

    screenshot_path.mkdir(parents=True, exist_ok=True)
    return str(screenshot_path)
