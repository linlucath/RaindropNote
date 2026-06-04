import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FrameDedupeResult:
    kept_paths: list[str]
    duplicate_paths: list[str]


def extract_time_from_frame_filename(filename: str) -> float:
    match = re.search(r"frame_(\d{2})_(\d{2})\.jpg", filename)
    if match:
        mm, ss = map(int, match.groups())
        return mm * 60 + ss
    return float("inf")


def group_frame_paths(image_paths: Sequence[str], grid_size: tuple[int, int]) -> list[list[str]]:
    sorted_paths = sorted(
        image_paths,
        key=lambda path: extract_time_from_frame_filename(os.path.basename(path)),
    )
    group_size = grid_size[0] * grid_size[1]
    return [sorted_paths[i:i + group_size] for i in range(0, len(sorted_paths), group_size)]


def select_unique_adjacent_frames(
    image_paths: Sequence[str],
    hash_file: Callable[[str], str],
) -> FrameDedupeResult:
    kept_paths: list[str] = []
    duplicate_paths: list[str] = []
    last_hash: str | None = None

    for path in image_paths:
        frame_hash = hash_file(path)
        if frame_hash == last_hash:
            duplicate_paths.append(path)
            continue
        last_hash = frame_hash
        kept_paths.append(path)

    return FrameDedupeResult(kept_paths=kept_paths, duplicate_paths=duplicate_paths)
