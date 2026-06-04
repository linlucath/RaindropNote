import os


SUPPORTED_FORMATS = {
    "pdf": "PDF 文档",
    "html": "HTML 网页",
    "word": "Word 文档 (.docx)",
    "docx": "Word 文档 (.docx)",
    "image": "PNG 图片",
    "png": "PNG 图片",
}
SUPPORTED_FORMAT_LABELS = ["pdf", "html", "word/docx", "image/png"]
FORMAT_RENDERER_KEYS = {
    "pdf": "pdf",
    "html": "html",
    "word": "word",
    "docx": "word",
    "image": "image",
    "png": "image",
}


def get_supported_formats() -> dict[str, str]:
    return dict(SUPPORTED_FORMATS)


def raise_unsupported_format(output_format: str):
    raise ValueError(
        f"不支持的导出格式: {output_format}. 支持的格式: {', '.join(SUPPORTED_FORMAT_LABELS)}"
    )


def build_export_renderers(exporter) -> dict[str, object]:
    return {
        "pdf": exporter._to_pdf,
        "html": lambda content, title: getattr(exporter, "_to_html")(content, title),
        "word": lambda content, title: getattr(exporter, "_to_word")(content, title),
        "image": lambda content, title: getattr(exporter, "_to_image")(content, title),
    }


def export_processed_content(
    output_format: str,
    title: str,
    content: str,
    renderers: dict[str, object],
    unsupported_format,
    logger,
) -> str:
    try:
        renderer_key = FORMAT_RENDERER_KEYS.get(output_format)
        if renderer_key is None:
            unsupported_format(output_format)

        save_path = renderers[renderer_key](content, title)
        logger.info("导出完成: %s", save_path)
        return save_path

    except Exception as e:
        logger.error("导出失败: %s", e)
        raise e


def export_pdf(content: str, title: str, save_dir: str, markdown_pdf_cls, section_cls, logger) -> str:
    try:
        pdf = markdown_pdf_cls(optimize=True)
        pdf.add_section(section_cls(content))

        save_path = os.path.join(save_dir, f"{title}.pdf")
        pdf.save(save_path)

        logger.info("PDF 导出成功: %s", save_path)
        return save_path

    except Exception as e:
        logger.warning("PDF 导出失败: %s", e)
        logger.info("尝试使用基本配置...")
        try:
            pdf = markdown_pdf_cls()
            pdf.add_section(section_cls(content))
            save_path = os.path.join(save_dir, f"{title}.pdf")
            pdf.save(save_path)
            logger.info("基本配置 PDF 导出成功: %s", save_path)
            return save_path
        except Exception as e2:
            logger.error("基本配置也失败: %s", e2)
            raise e2
