import json
from typing import Iterable, Iterator, Tuple


def build_create_upload_payload(file_size: int) -> str:
    return json.dumps({
        "type": 2,
        "name": "audio.mp3",
        "size": file_size,
        "ResourceFileType": "mp3",
        "model_id": "8",
    })


def build_commit_upload_payload(
    *,
    in_boss_key: str,
    resource_id: str,
    etags: Iterable[str],
    upload_id: str,
) -> str:
    return json.dumps({
        "InBossKey": in_boss_key,
        "ResourceId": resource_id,
        "Etags": ",".join(etags),
        "UploadId": upload_id,
        "model_id": "8",
    })


def iter_upload_clip_ranges(file_size: int, per_size: int, clips: int) -> Iterator[Tuple[int, int]]:
    for clip in range(clips):
        start_range = clip * per_size
        end_range = min((clip + 1) * per_size, file_size)
        yield start_range, end_range
