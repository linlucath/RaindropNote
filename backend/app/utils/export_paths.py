import base64
import mimetypes
import os
import re
from collections.abc import Callable
from typing import Match


REMOTE_IMAGE_PREFIXES = ("http://", "https://", "data:")
MARKDOWN_IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

FALLBACK_IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


def normalize_path(path: str | os.PathLike[str]) -> str:
    return os.path.normpath(os.path.abspath(os.fspath(path)))


def image_mime_type(img_path: str | os.PathLike[str]) -> str:
    img_path = os.fspath(img_path)
    mime_type, _ = mimetypes.guess_type(img_path)
    if mime_type:
        return mime_type

    ext = os.path.splitext(img_path)[1].lower()
    return FALLBACK_IMAGE_MIME_TYPES.get(ext, "image/png")


def embed_image_as_base64(img_path: str | os.PathLike[str], logger=None) -> str | None:
    img_path = os.fspath(img_path)
    try:
        with open(img_path, "rb") as f:
            img_data = f.read()

        base64_data = base64.b64encode(img_data).decode("utf-8")
        return f"data:{image_mime_type(img_path)};base64,{base64_data}"
    except Exception as e:
        if logger is not None:
            logger.warning("图片 base64 编码失败 %s: %s", img_path, e)
        return None


def static_path_to_absolute(
    img_path: str,
    static_dir: str | os.PathLike[str],
) -> str:
    relative_path = img_path[len("/static/"):]
    return normalize_path(os.path.join(os.fspath(static_dir), relative_path))


def relative_path_candidates(
    img_path: str,
    relative_image_dir: str | os.PathLike[str],
    base_dir: str | os.PathLike[str],
) -> list[str]:
    return [
        os.path.join(os.fspath(relative_image_dir), img_path),
        os.path.abspath(img_path),
        os.path.join(os.fspath(base_dir), img_path),
    ]


def resolve_export_target(output_path: str | os.PathLike[str]) -> tuple[str, str]:
    output_path = os.fspath(output_path)
    output_dir = os.path.dirname(os.path.abspath(output_path)) or os.getcwd()
    title = os.path.splitext(os.path.basename(output_path))[0]
    return output_dir, title


def build_debug_paths(
    *,
    base_dir: str,
    data_dir: str,
    save_path: str,
    static_base: str,
    image_base_url: str | None,
) -> dict[str, str | None]:
    return {
        "BASE_DIR": base_dir,
        "DATA_DIR": data_dir,
        "SAVE_PATH": save_path,
        "STATIC_BASE": static_base,
        "IMAGE_BASE_URL": image_base_url,
    }


def print_debug_paths(paths: dict[str, str | None]) -> None:
    print("=== 路径调试信息 ===")
    print(f"BASE_DIR: {paths['BASE_DIR']}")
    print(f"DATA_DIR: {paths['DATA_DIR']}")
    print(f"SAVE_PATH: {paths['SAVE_PATH']}")
    print(f"STATIC_BASE: {paths['STATIC_BASE']}")
    print(f"IMAGE_BASE_URL: {paths['IMAGE_BASE_URL']}")
    print("==================")


def replace_markdown_image_paths(
    content: str,
    *,
    static_dir: str | os.PathLike[str],
    base_dir: str | os.PathLike[str],
    relative_image_dir: str | os.PathLike[str],
    embed_image: Callable[[str], str | None],
    image_pattern: re.Pattern[str] = MARKDOWN_IMAGE_PATTERN,
    remote_image_prefixes: tuple[str, ...] = REMOTE_IMAGE_PREFIXES,
    logger=None,
) -> str:
    def repl(match: Match[str]) -> str:
        alt_text = match.group(1) if match.group(1) else ""
        img_path = match.group(2).strip()

        if logger is not None:
            logger.debug("处理图片路径: %s", img_path)

        if img_path.startswith("/static/"):
            abs_path = static_path_to_absolute(img_path, static_dir)

            if os.path.exists(abs_path):
                base64_uri = embed_image(abs_path)
                if base64_uri:
                    if logger is not None:
                        logger.debug("图片转换为 base64 成功: %s", img_path)
                    return f"![{alt_text}]({base64_uri})"

                if logger is not None:
                    logger.warning("图片 base64 转换失败: %s", abs_path)
                return f"![{alt_text}](图片转换失败: {img_path})"

            if logger is not None:
                logger.warning("图片文件不存在: %s", abs_path)
            return f"![{alt_text}](图片不存在: {img_path})"

        if not img_path.startswith(remote_image_prefixes):
            for abs_path in relative_path_candidates(img_path, relative_image_dir, base_dir):
                abs_path = normalize_path(abs_path)
                if os.path.exists(abs_path):
                    base64_uri = embed_image(abs_path)
                    if base64_uri:
                        if logger is not None:
                            logger.debug("相对路径图片转换为 base64 成功: %s", img_path)
                        return f"![{alt_text}]({base64_uri})"
                    break

            if logger is not None:
                logger.warning("图片文件未找到: %s", img_path)
            return f"![{alt_text}](图片未找到: {img_path})"

        if logger is not None:
            logger.debug("网络图片或 data URI 保持不变: %s...", img_path[:50])
        return match.group(0)

    result = image_pattern.sub(repl, content)

    if logger is not None:
        logger.debug("图片路径处理完成")
    return result
