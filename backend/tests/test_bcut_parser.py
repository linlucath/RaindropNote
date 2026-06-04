import json

from app.transcriber.bcut_payloads import (
    build_commit_upload_payload,
    build_create_upload_payload,
    iter_upload_clip_ranges,
)
from app.transcriber.bcut_result_parser import parse_task_result


def test_parse_task_result_converts_utterances_to_transcript_result():
    raw_result = {
        "language": "zh",
        "utterances": [
            {"transcript": " 第一段 ", "start_time": 1200, "end_time": 3400},
            {"transcript": "第二段", "start_time": "3400", "end_time": "5600"},
        ],
    }
    task_resp = {"result": json.dumps(raw_result, ensure_ascii=False)}

    result = parse_task_result(task_resp["result"])

    assert result.language == "zh"
    assert result.full_text == "第一段 第二段"
    assert [(segment.start, segment.end, segment.text) for segment in result.segments] == [
        (1.2, 3.4, "第一段"),
        (3.4, 5.6, "第二段"),
    ]
    assert result.raw == raw_result


def test_bcut_payload_helpers_preserve_upload_contracts():
    assert json.loads(build_create_upload_payload(file_size=12345)) == {
        "type": 2,
        "name": "audio.mp3",
        "size": 12345,
        "ResourceFileType": "mp3",
        "model_id": "8",
    }

    assert json.loads(
        build_commit_upload_payload(
            in_boss_key="boss-key",
            resource_id="resource-id",
            etags=["etag-1", "etag-2"],
            upload_id="upload-id",
        )
    ) == {
        "InBossKey": "boss-key",
        "ResourceId": "resource-id",
        "Etags": "etag-1,etag-2",
        "UploadId": "upload-id",
        "model_id": "8",
    }

    assert list(iter_upload_clip_ranges(file_size=10, per_size=4, clips=3)) == [
        (0, 4),
        (4, 8),
        (8, 10),
    ]
