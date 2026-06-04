import importlib.util
import io
import pathlib
import re
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


_STUBBED_MODULE_NAMES = (
    "app",
    "app.utils",
    "app.utils.video_frame_dedupe",
    "app.utils.logger",
    "app.utils.path_helper",
    "ffmpeg",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
)


def _snapshot_modules():
    return {name: sys.modules.get(name) for name in _STUBBED_MODULE_NAMES}


def _restore_modules(snapshot):
    for name, module in snapshot.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


def _install_stubs():
    root = pathlib.Path(__file__).resolve().parents[1]

    app_mod = types.ModuleType("app")
    utils_pkg = types.ModuleType("app.utils")
    utils_pkg.__path__ = [str(root / "app" / "utils")]

    logger_mod = types.ModuleType("app.utils.logger")

    class _Logger:
        @staticmethod
        def debug(*_args, **_kwargs):
            return None

        @staticmethod
        def info(*_args, **_kwargs):
            return None

        @staticmethod
        def warning(*_args, **_kwargs):
            return None

        @staticmethod
        def error(*_args, **_kwargs):
            return None

    def _get_logger(_name):
        return _Logger()

    logger_mod.get_logger = _get_logger

    path_helper_mod = types.ModuleType("app.utils.path_helper")
    ffmpeg_mod = types.ModuleType("ffmpeg")

    pil_mod = types.ModuleType("PIL")
    pil_image_mod = types.ModuleType("PIL.Image")
    pil_draw_mod = types.ModuleType("PIL.ImageDraw")
    pil_font_mod = types.ModuleType("PIL.ImageFont")

    class _FakeImage:
        pass

    class _FakeImageDraw:
        @staticmethod
        def Draw(*_args, **_kwargs):
            return None

    class _FakeImageFont:
        @staticmethod
        def truetype(*_args, **_kwargs):
            return None

        @staticmethod
        def load_default():
            return None

    pil_image_mod.Image = _FakeImage
    pil_draw_mod.ImageDraw = _FakeImageDraw
    pil_font_mod.ImageFont = _FakeImageFont

    def _get_app_dir(name):
        return name

    path_helper_mod.get_app_dir = _get_app_dir
    ffmpeg_mod.probe = lambda *_args, **_kwargs: {"format": {"duration": "0"}}

    sys.modules.setdefault("app", app_mod)
    sys.modules.setdefault("app.utils", utils_pkg)
    sys.modules["PIL"] = pil_mod
    sys.modules["PIL.Image"] = pil_image_mod
    sys.modules["PIL.ImageDraw"] = pil_draw_mod
    sys.modules["PIL.ImageFont"] = pil_font_mod
    sys.modules["ffmpeg"] = ffmpeg_mod
    sys.modules["app.utils.logger"] = logger_mod
    sys.modules["app.utils.path_helper"] = path_helper_mod


def _load_video_reader_module():
    module_snapshot = _snapshot_modules()
    _install_stubs()
    try:
        root = pathlib.Path(__file__).resolve().parents[1]
        module_path = root / "app" / "utils" / "video_reader.py"
        spec = importlib.util.spec_from_file_location("video_reader", module_path)
        if spec is None or spec.loader is None:
            raise ImportError("video_reader module spec not found")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        _restore_modules(module_snapshot)


def _load_video_frame_dedupe_module():
    root = pathlib.Path(__file__).resolve().parents[1]
    module_path = root / "app" / "utils" / "video_frame_dedupe.py"
    spec = importlib.util.spec_from_file_location("video_frame_dedupe", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("video_frame_dedupe module spec not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


video_reader_module = _load_video_reader_module()
VideoReader = video_reader_module.VideoReader


def _make_fake_ffmpeg_runner(colors_by_second):
    def _runner(cmd, check=True):
        output_path = next((arg for arg in cmd if isinstance(arg, str) and arg.endswith(".jpg")), None)
        if output_path is None:
            raise AssertionError("Output path not found in ffmpeg cmd")
        match = re.search(r"frame_(\d{2})_(\d{2})\.jpg$", output_path)
        if match is None:
            raise AssertionError("Unexpected output path")
        sec = int(match.group(1)) * 60 + int(match.group(2))
        payload = colors_by_second[sec]
        with open(output_path, "wb") as f:
            f.write(payload)
        return 0

    return _runner


class TestVideoReaderDeduplicateFrames(unittest.TestCase):
    def test_helper_groups_frame_paths_by_timestamp_then_grid_size(self):
        module = _load_video_frame_dedupe_module()

        paths = [
            "/tmp/frame_00_06.jpg",
            "/tmp/frame_00_00.jpg",
            "/tmp/frame_00_04.jpg",
            "/tmp/frame_00_02.jpg",
            "/tmp/frame_00_08.jpg",
        ]

        groups = module.group_frame_paths(paths, grid_size=(2, 2))

        self.assertEqual(
            groups,
            [
                [
                    "/tmp/frame_00_00.jpg",
                    "/tmp/frame_00_02.jpg",
                    "/tmp/frame_00_04.jpg",
                    "/tmp/frame_00_06.jpg",
                ],
                ["/tmp/frame_00_08.jpg"],
            ],
        )

    def test_helper_keeps_non_adjacent_matching_hashes(self):
        module = _load_video_frame_dedupe_module()

        paths = ["first.jpg", "duplicate.jpg", "changed.jpg", "repeat-first.jpg"]
        hashes = {
            "first.jpg": "same",
            "duplicate.jpg": "same",
            "changed.jpg": "changed",
            "repeat-first.jpg": "same",
        }

        result = module.select_unique_adjacent_frames(paths, hash_file=hashes.__getitem__)

        self.assertEqual(result.kept_paths, ["first.jpg", "changed.jpg", "repeat-first.jpg"])
        self.assertEqual(result.duplicate_paths, ["duplicate.jpg"])

    def test_video_reader_wrappers_keep_legacy_paths(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_dir = pathlib.Path(tmp_dir) / "frames"
            frame_dir.mkdir()
            grid_dir = pathlib.Path(tmp_dir) / "grids"
            for name in ("frame_00_04.jpg", "frame_00_00.jpg", "frame_00_02.jpg"):
                (frame_dir / name).write_bytes(b"")

            reader = VideoReader(
                video_path="dummy.mp4",
                grid_size=(2, 1),
                frame_dir=str(frame_dir),
                grid_dir=str(grid_dir),
            )

            self.assertEqual(reader.extract_time_from_filename("frame_01_02.jpg"), 62)
            self.assertEqual(reader.extract_time_from_filename("not-a-frame.jpg"), float("inf"))
            self.assertEqual(
                [[pathlib.Path(path).name for path in group] for group in reader.group_images()],
                [["frame_00_00.jpg", "frame_00_02.jpg"], ["frame_00_04.jpg"]],
            )

    def test_extract_frames_skips_adjacent_duplicates_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_dir = pathlib.Path(tmp_dir) / "frames"
            grid_dir = pathlib.Path(tmp_dir) / "grids"
            reader = VideoReader(
                video_path="dummy.mp4",
                frame_interval=1,
                frame_dir=str(frame_dir),
                grid_dir=str(grid_dir),
            )

            fake_colors = {
                0: b"frame-a",
                1: b"frame-a",
                2: b"frame-b",
                3: b"frame-b",
            }

            with patch.object(video_reader_module.ffmpeg, "probe", return_value={"format": {"duration": "4"}}), \
                    patch.object(video_reader_module.subprocess, "run", side_effect=_make_fake_ffmpeg_runner(fake_colors)):
                paths = reader.extract_frames(max_frames=10)

            names = [pathlib.Path(p).name for p in paths]
            self.assertEqual(names, ["frame_00_00.jpg", "frame_00_02.jpg"])

    def test_constructor_and_run_do_not_print_debug_paths(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_dir = pathlib.Path(tmp_dir) / "frames"
            grid_dir = pathlib.Path(tmp_dir) / "grids"
            output = io.StringIO()

            with redirect_stdout(output):
                reader = VideoReader(
                    video_path="dummy.mp4",
                    frame_interval=1,
                    frame_dir=str(frame_dir),
                    grid_dir=str(grid_dir),
                )
                with patch.object(reader, "extract_frames", return_value=[]), \
                        patch.object(reader, "group_images", return_value=[]), \
                        patch.object(reader, "encode_images_to_base64", return_value=[]):
                    self.assertEqual(reader.run(), [])

            self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
