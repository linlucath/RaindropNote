import os
import logging
from markdown_pdf import MarkdownPdf, Section
from dotenv import load_dotenv

try:
    from app.utils import export_paths, export_rendering
except ModuleNotFoundError:
    import importlib.util

    def _load_sibling_module(module_name: str):
        module_path = os.path.join(os.path.dirname(__file__), f"{module_name}.py")
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"{module_name} module spec not found")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    export_paths = _load_sibling_module("export_paths")
    export_rendering = _load_sibling_module("export_rendering")

load_dotenv()

logger = logging.getLogger(__name__)

# 项目根路径（无论你在哪里运行）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 从 .env 获取 DATA_DIR，相对于 BASE_DIR 解析
DATA_DIR_NAME = os.getenv("DATA_DIR", "data")
DATA_DIR = os.path.join(BASE_DIR, DATA_DIR_NAME)
SAVE_PATH = os.path.join(DATA_DIR, "note_output")
IMAGE_BASE_URL = os.getenv("IMAGE_BASE_URL")
STATIC_BASE = os.path.join(BASE_DIR, IMAGE_BASE_URL) if IMAGE_BASE_URL else os.path.join(BASE_DIR, "static")

SUPPORTED_FORMATS = export_rendering.SUPPORTED_FORMATS
SUPPORTED_FORMAT_LABELS = export_rendering.SUPPORTED_FORMAT_LABELS
REMOTE_IMAGE_PREFIXES = export_paths.REMOTE_IMAGE_PREFIXES
MARKDOWN_IMAGE_PATTERN = export_paths.MARKDOWN_IMAGE_PATTERN


def _raise_unsupported_format(output_format: str):
    return export_rendering.raise_unsupported_format(output_format)


def get_supported_formats():
    """
    返回支持的导出格式列表
    """
    return export_rendering.get_supported_formats()


class MarkdownImageProcessor:
    def __init__(self, static_dir=None, base_dir: str = BASE_DIR, relative_image_dir=None):
        self.base_dir = os.fspath(base_dir)
        self.static_dir = os.fspath(static_dir) if static_dir is not None else os.path.join(self.base_dir, "static")
        self.relative_image_dir = (
            os.fspath(relative_image_dir) if relative_image_dir is not None else self.static_dir
        )

    def embed_image_as_base64(self, img_path: str) -> str:
        """
        将图片转换为 base64 格式嵌入
        """
        return export_paths.embed_image_as_base64(img_path, logger=logger)

    def get_normalized_path(self, path: str) -> str:
        """
        获取规范化的绝对路径
        """
        return export_paths.normalize_path(path)

    def _static_path_to_absolute(self, img_path: str) -> str:
        return export_paths.static_path_to_absolute(img_path, self.static_dir)

    def _relative_path_candidates(self, img_path: str):
        return export_paths.relative_path_candidates(
            img_path,
            self.relative_image_dir,
            self.base_dir,
        )

    def replace_static_paths_with_embedded_images(self, content: str) -> str:
        """
        将 Markdown 中的图片路径替换为 base64 内嵌格式
        这样可以确保图片在 PDF 中正确显示
        """
        return export_paths.replace_markdown_image_paths(
            content,
            static_dir=self.static_dir,
            base_dir=self.base_dir,
            relative_image_dir=self.relative_image_dir,
            embed_image=self.embed_image_as_base64,
            image_pattern=MARKDOWN_IMAGE_PATTERN,
            remote_image_prefixes=REMOTE_IMAGE_PREFIXES,
            logger=logger,
        )


def export(markdown_content: str, output_path: str, format_type: str, static_dir=None) -> str:
    """
    导出 Markdown 内容为指定格式。
    """
    content = markdown_content.strip()

    logger.debug("开始处理图片路径...")
    content = MarkdownImageProcessor(static_dir=static_dir).replace_static_paths_with_embedded_images(content)

    output_format = format_type.lower()
    if output_format not in SUPPORTED_FORMATS:
        _raise_unsupported_format(output_format)

    output_dir, title = export_paths.resolve_export_target(output_path)
    exporter = ExportUtils(static_dir=static_dir, save_path=output_dir)
    return exporter._export_processed_content(output_format, title, content)


class ExportUtils:
    def __init__(self, **kwargs):
        self.save_path = os.fspath(kwargs.get("save_path", SAVE_PATH))
        self._image_processor = MarkdownImageProcessor(
            static_dir=kwargs.get("static_dir"),
            relative_image_dir=kwargs.get("relative_image_dir", STATIC_BASE),
        )
        # 确认SAVE_PATH存在
        logger.debug("保存路径: %s", self.save_path)
        logger.debug("静态文件路径: %s", STATIC_BASE)
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)

    def _embed_image_as_base64(self, img_path: str) -> str:
        """
        将图片转换为 base64 格式嵌入
        """
        return self._image_processor.embed_image_as_base64(img_path)

    def _get_normalized_path(self, path: str) -> str:
        """
        获取规范化的绝对路径
        """
        return self._image_processor.get_normalized_path(path)

    def _replace_static_paths_with_absolute(self, content: str) -> str:
        """
        将 Markdown 中的图片路径替换为 base64 内嵌格式
        这样可以确保图片在 PDF 中正确显示
        """
        return self._image_processor.replace_static_paths_with_embedded_images(content)

    def _to_pdf(self, content: str, title: str):
        """
        将 Markdown 内容转换为 PDF
        """
        return export_rendering.export_pdf(
            content,
            title,
            self.save_path,
            MarkdownPdf,
            Section,
            logger,
        )

    def export(self, output_format: str, title: str, content: str) -> str:
        """
        导出内容为指定格式
        支持格式：pdf, html, word/docx, image/png
        """
        content = content.strip()

        # 处理图片路径
        logger.debug("开始处理图片路径...")
        content = self._replace_static_paths_with_absolute(content)

        output_format = output_format.lower()
        return self._export_processed_content(output_format, title, content)

    def _export_processed_content(self, output_format: str, title: str, content: str) -> str:
        return export_rendering.export_processed_content(
            output_format,
            title,
            content,
            export_rendering.build_export_renderers(self),
            _raise_unsupported_format,
            logger,
        )

    def get_supported_formats(self):
        """
        返回支持的导出格式列表
        """
        return get_supported_formats()

    def debug_paths(self):
        """
        调试方法：打印重要路径信息
        """
        export_paths.print_debug_paths(
            export_paths.build_debug_paths(
                base_dir=BASE_DIR,
                data_dir=DATA_DIR,
                save_path=SAVE_PATH,
                static_base=STATIC_BASE,
                image_base_url=IMAGE_BASE_URL,
            )
        )
