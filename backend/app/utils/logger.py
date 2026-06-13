import logging
import sys
from pathlib import Path

from app.utils.path_helper import get_app_dir

# 日志格式
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# 控制台输出
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

def get_log_dir() -> Path:
    log_dir = Path(get_app_dir("logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def build_file_handler() -> logging.Handler | None:
    try:
        file_handler = logging.FileHandler(get_log_dir() / "app.log", encoding="utf-8")
    except OSError:
        return None

    file_handler.setFormatter(formatter)
    return file_handler

# 获取日志器

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logger.addHandler(console_handler)
        file_handler = build_file_handler()
        if file_handler is not None:
            logger.addHandler(file_handler)
        logger.propagate = False
    return logger
