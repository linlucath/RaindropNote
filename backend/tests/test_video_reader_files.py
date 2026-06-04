import base64
import hashlib
import importlib.util
import pathlib
import tempfile
import unittest


def _load_video_reader_files_module():
    root = pathlib.Path(__file__).resolve().parents[1]
    module_path = root / "app" / "utils" / "video_reader_files.py"
    spec = importlib.util.spec_from_file_location("video_reader_files", module_path)
    if spec is None or spec.loader is None:
        raise ImportError("video_reader_files module spec not found")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestVideoReaderFileHelpers(unittest.TestCase):
    def test_collect_existing_frame_paths_preserves_timestamp_order(self):
        module = _load_video_reader_files_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            frame_dir = pathlib.Path(tmp_dir)
            first = frame_dir / "frame_00_00.jpg"
            later = frame_dir / "frame_00_04.jpg"
            missing = frame_dir / "frame_00_02.jpg"
            first.write_bytes(b"first")
            later.write_bytes(b"later")

            paths = module.collect_existing_frame_paths(
                timestamps=[0, 2, 4],
                frame_results={
                    4: str(later),
                    0: str(first),
                    2: str(missing),
                },
            )

        self.assertEqual(paths, [str(first), str(later)])

    def test_remove_files_with_prefix_keeps_unmatched_files(self):
        module = _load_video_reader_files_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            target_dir = pathlib.Path(tmp_dir)
            (target_dir / "frame_00_00.jpg").write_bytes(b"frame")
            (target_dir / "frame_00_02.jpg").write_bytes(b"frame")
            keep = target_dir / "notes.txt"
            keep.write_text("keep", encoding="utf-8")

            module.remove_files_with_prefix(str(target_dir), "frame_")

            self.assertFalse((target_dir / "frame_00_00.jpg").exists())
            self.assertFalse((target_dir / "frame_00_02.jpg").exists())
            self.assertTrue(keep.exists())

    def test_calculate_file_md5_hashes_file_contents(self):
        module = _load_video_reader_files_module()

        with tempfile.NamedTemporaryFile() as file:
            payload = b"hash me in chunks"
            file.write(payload)
            file.flush()

            digest = module.calculate_file_md5(file.name)

        self.assertEqual(digest, hashlib.md5(payload).hexdigest())

    def test_encode_jpeg_files_to_data_urls_preserves_input_order(self):
        module = _load_video_reader_files_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            image_dir = pathlib.Path(tmp_dir)
            first = image_dir / "first.jpg"
            second = image_dir / "second.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")

            urls = module.encode_jpeg_files_to_data_urls([str(first), str(second)])

        self.assertEqual(
            urls,
            [
                f"data:image/jpeg;base64,{base64.b64encode(b'first').decode('utf-8')}",
                f"data:image/jpeg;base64,{base64.b64encode(b'second').decode('utf-8')}",
            ],
        )


if __name__ == "__main__":
    unittest.main()
