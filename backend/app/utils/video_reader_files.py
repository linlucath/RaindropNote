import base64
import hashlib
import os
from collections.abc import Iterable, Mapping, Sequence


def calculate_file_md5(file_path: str) -> str:
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def collect_existing_frame_paths(
    timestamps: Sequence[int],
    frame_results: Mapping[int, str | None],
) -> list[str]:
    image_paths = []
    for ts in timestamps:
        output_path = frame_results.get(ts)
        if not output_path or not os.path.exists(output_path):
            continue
        image_paths.append(output_path)
    return image_paths


def remove_file_paths(paths: Iterable[str]) -> None:
    for path in paths:
        os.remove(path)


def remove_files_with_prefix(directory: str, prefix: str) -> None:
    for file in os.listdir(directory):
        if file.startswith(prefix):
            os.remove(os.path.join(directory, file))


def encode_jpeg_files_to_data_urls(image_paths: Sequence[str]) -> list[str]:
    base64_images = []
    for path in image_paths:
        with open(path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode("utf-8")
            base64_images.append(f"data:image/jpeg;base64,{encoded_string}")
    return base64_images
