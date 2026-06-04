import base64
import contextlib
import importlib.util
import io
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "app" / "utils" / "export.py"
spec = importlib.util.spec_from_file_location("export_utils", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("export utils module spec not found")
export_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_utils)


class TestExportUtils(unittest.TestCase):
    def test_export_utils_init_does_not_print_save_or_static_paths_to_stdout(self):
        with tempfile.TemporaryDirectory() as static_dir, tempfile.TemporaryDirectory() as save_path:
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                export_utils.ExportUtils(static_dir=static_dir, save_path=save_path)

        output = stdout.getvalue()
        self.assertNotIn("保存路径", output)
        self.assertNotIn("静态文件路径", output)
        self.assertEqual(output, "")

    def test_http_and_https_image_urls_are_not_rewritten(self):
        processor = export_utils.MarkdownImageProcessor(static_dir=ROOT / "static")
        markdown = (
            "![remote](https://example.com/a.png)\n"
            "![remote2](http://example.com/b.jpg)"
        )

        result = processor.replace_static_paths_with_embedded_images(markdown)

        self.assertEqual(result, markdown)

    def test_data_image_urls_are_not_rewritten(self):
        processor = export_utils.MarkdownImageProcessor(static_dir=ROOT / "static")
        markdown = "![inline](data:image/png;base64,abc123)"

        result = processor.replace_static_paths_with_embedded_images(markdown)

        self.assertEqual(result, markdown)

    def test_static_image_path_uses_static_dir_and_embeds_base64(self):
        with tempfile.TemporaryDirectory() as static_dir:
            image_dir = pathlib.Path(static_dir) / "export-test"
            image_dir.mkdir()
            image_path = image_dir / "tiny.png"
            image_bytes = b"\x89PNG\r\n\x1a\n"
            image_path.write_bytes(image_bytes)
            processor = export_utils.MarkdownImageProcessor(static_dir=static_dir)

            result = processor.replace_static_paths_with_embedded_images(
                "![tiny](/static/export-test/tiny.png)"
            )

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        self.assertEqual(result, f"![tiny](data:image/png;base64,{encoded})")

    def test_existing_export_utils_static_replacement_method_still_embeds(self):
        with tempfile.TemporaryDirectory() as static_dir, tempfile.TemporaryDirectory() as save_path:
            image_path = pathlib.Path(static_dir) / "tiny.png"
            image_bytes = b"\x89PNG\r\n\x1a\n"
            image_path.write_bytes(image_bytes)
            exporter = export_utils.ExportUtils(static_dir=static_dir, save_path=save_path)

            result = exporter._replace_static_paths_with_absolute("![tiny](/static/tiny.png)")

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        self.assertEqual(result, f"![tiny](data:image/png;base64,{encoded})")

    def test_existing_static_base_monkeypatch_still_controls_relative_images(self):
        original_static_base = export_utils.STATIC_BASE
        try:
            with tempfile.TemporaryDirectory() as static_base, tempfile.TemporaryDirectory() as save_path:
                image_path = pathlib.Path(static_base) / "relative.png"
                image_bytes = b"\x89PNG\r\n\x1a\nrelative"
                image_path.write_bytes(image_bytes)
                export_utils.STATIC_BASE = static_base
                exporter = export_utils.ExportUtils(save_path=save_path)

                result = exporter._replace_static_paths_with_absolute("![tiny](relative.png)")
        finally:
            export_utils.STATIC_BASE = original_static_base

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        self.assertEqual(result, f"![tiny](data:image/png;base64,{encoded})")

    def test_existing_export_utils_path_and_embed_methods_are_preserved(self):
        with tempfile.TemporaryDirectory() as static_dir, tempfile.TemporaryDirectory() as save_path:
            image_path = pathlib.Path(static_dir) / "tiny.unknown"
            image_bytes = b"image-bytes"
            image_path.write_bytes(image_bytes)
            exporter = export_utils.ExportUtils(static_dir=static_dir, save_path=save_path)

            normalized = exporter._get_normalized_path(image_path)
            embedded = exporter._embed_image_as_base64(str(image_path))

        self.assertEqual(normalized, str(image_path))
        self.assertEqual(
            embedded,
            f"data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}",
        )

    def test_missing_local_image_does_not_crash_markdown_processing(self):
        processor = export_utils.MarkdownImageProcessor(static_dir=ROOT / "static")

        result = processor.replace_static_paths_with_embedded_images(
            "before ![missing](missing-image.png) after"
        )

        self.assertEqual(
            result,
            "before ![missing](图片未找到: missing-image.png) after",
        )

    def test_missing_static_image_uses_existing_missing_image_markdown_text(self):
        with tempfile.TemporaryDirectory() as static_dir:
            processor = export_utils.MarkdownImageProcessor(static_dir=static_dir)

            result = processor.replace_static_paths_with_embedded_images(
                "before ![missing](/static/missing-image.png) after"
            )

        self.assertEqual(
            result,
            "before ![missing](图片不存在: /static/missing-image.png) after",
        )

    def test_embed_image_as_base64_returns_none_when_file_read_fails(self):
        with tempfile.TemporaryDirectory() as static_dir, tempfile.TemporaryDirectory() as save_path:
            exporter = export_utils.ExportUtils(static_dir=static_dir, save_path=save_path)

            result = exporter._embed_image_as_base64(str(pathlib.Path(static_dir) / "missing.png"))

        self.assertIsNone(result)

    def test_pdf_export_still_uses_module_level_pdf_classes_for_monkeypatching(self):
        class FakePdf:
            instances = []

            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.sections = []
                self.saved_path = None
                self.__class__.instances.append(self)

            def add_section(self, section):
                self.sections.append(section)

            def save(self, path):
                self.saved_path = path

        class FakeSection:
            def __init__(self, content):
                self.content = content

        original_pdf = export_utils.MarkdownPdf
        original_section = export_utils.Section
        try:
            export_utils.MarkdownPdf = FakePdf
            export_utils.Section = FakeSection
            with tempfile.TemporaryDirectory() as save_path:
                exporter = export_utils.ExportUtils(static_dir=save_path, save_path=save_path)

                result = exporter._to_pdf("# Body", "note")
        finally:
            export_utils.MarkdownPdf = original_pdf
            export_utils.Section = original_section

        expected_path = str(pathlib.Path(save_path) / "note.pdf")
        self.assertEqual(result, expected_path)
        self.assertEqual(FakePdf.instances[0].kwargs, {"optimize": True})
        self.assertEqual(FakePdf.instances[0].sections[0].content, "# Body")
        self.assertEqual(FakePdf.instances[0].saved_path, expected_path)

    def test_export_processed_content_delegates_dispatch_to_rendering_helper(self):
        original_export_processed_content = export_utils.export_rendering.export_processed_content
        calls = []

        def fake_export_processed_content(
            output_format,
            title,
            content,
            renderers,
            unsupported_format,
            logger,
        ):
            calls.append(
                {
                    "output_format": output_format,
                    "title": title,
                    "content": content,
                    "renderer_keys": sorted(renderers),
                    "unsupported_format": unsupported_format,
                    "logger": logger,
                }
            )
            return "/tmp/delegated"

        try:
            export_utils.export_rendering.export_processed_content = fake_export_processed_content
            with tempfile.TemporaryDirectory() as static_dir, tempfile.TemporaryDirectory() as save_path:
                exporter = export_utils.ExportUtils(static_dir=static_dir, save_path=save_path)

                result = exporter._export_processed_content("html", "note", "# Body")
        finally:
            export_utils.export_rendering.export_processed_content = original_export_processed_content

        self.assertEqual(result, "/tmp/delegated")
        self.assertEqual(
            calls,
            [
                {
                    "output_format": "html",
                    "title": "note",
                    "content": "# Body",
                    "renderer_keys": ["html", "image", "pdf", "word"],
                    "unsupported_format": export_utils._raise_unsupported_format,
                    "logger": export_utils.logger,
                }
            ],
        )

    def test_rendering_dispatch_helper_preserves_format_aliases(self):
        calls = []
        renderers = {
            "pdf": lambda content, title: calls.append(("pdf", content, title)) or "note.pdf",
            "html": lambda content, title: calls.append(("html", content, title)) or "note.html",
            "word": lambda content, title: calls.append(("word", content, title)) or "note.docx",
            "image": lambda content, title: calls.append(("image", content, title)) or "note.png",
        }

        with self.subTest("docx"):
            result = export_utils.export_rendering.export_processed_content(
                "docx",
                "note",
                "# Body",
                renderers,
                export_utils._raise_unsupported_format,
                export_utils.logger,
            )
            self.assertEqual(result, "note.docx")

        with self.subTest("png"):
            result = export_utils.export_rendering.export_processed_content(
                "png",
                "note",
                "# Body",
                renderers,
                export_utils._raise_unsupported_format,
                export_utils.logger,
            )
            self.assertEqual(result, "note.png")

        self.assertEqual(
            calls,
            [
                ("word", "# Body", "note"),
                ("image", "# Body", "note"),
            ],
        )

    def test_debug_paths_delegates_to_export_paths_helper(self):
        sentinel = object()
        original_print_debug_paths = getattr(export_utils.export_paths, "print_debug_paths", sentinel)
        calls = []

        def fake_print_debug_paths(paths):
            calls.append(paths)

        try:
            export_utils.export_paths.print_debug_paths = fake_print_debug_paths
            with tempfile.TemporaryDirectory() as static_dir, tempfile.TemporaryDirectory() as save_path:
                exporter = export_utils.ExportUtils(static_dir=static_dir, save_path=save_path)

                exporter.debug_paths()
        finally:
            if original_print_debug_paths is sentinel:
                delattr(export_utils.export_paths, "print_debug_paths")
            else:
                export_utils.export_paths.print_debug_paths = original_print_debug_paths

        self.assertEqual(
            calls,
            [
                {
                    "BASE_DIR": export_utils.BASE_DIR,
                    "DATA_DIR": export_utils.DATA_DIR,
                    "SAVE_PATH": export_utils.SAVE_PATH,
                    "STATIC_BASE": export_utils.STATIC_BASE,
                    "IMAGE_BASE_URL": export_utils.IMAGE_BASE_URL,
                }
            ],
        )

    def test_get_supported_formats_returns_existing_mapping(self):
        self.assertEqual(
            export_utils.get_supported_formats(),
            {
                "pdf": "PDF 文档",
                "html": "HTML 网页",
                "word": "Word 文档 (.docx)",
                "docx": "Word 文档 (.docx)",
                "image": "PNG 图片",
                "png": "PNG 图片",
            },
        )

    def test_module_get_supported_formats_matches_export_utils_method(self):
        with tempfile.TemporaryDirectory() as static_dir, tempfile.TemporaryDirectory() as save_path:
            exporter = export_utils.ExportUtils(static_dir=static_dir, save_path=save_path)

            instance_formats = exporter.get_supported_formats()

        self.assertEqual(export_utils.get_supported_formats(), instance_formats)
        self.assertIsNot(export_utils.get_supported_formats(), instance_formats)

    def test_export_rejects_unsupported_format(self):
        with self.assertRaisesRegex(ValueError, "不支持的导出格式: txt"):
            export_utils.export("# note", "note", "txt", static_dir=ROOT / "static")


if __name__ == "__main__":
    unittest.main()
