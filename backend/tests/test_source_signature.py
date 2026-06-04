from unittest.mock import Mock

from app.gpt.universal_gpt import UniversalGPT
from app.models.gpt_model import GPTSource
from app.models.transcriber_model import TranscriptSegment


def test_source_signature_helper_matches_universal_gpt_wrapper():
    from app.gpt.source_signature import build_source_signature

    source = GPTSource(
        title="视频标题",
        tags=["tag-a", "tag-b"],
        _format=["toc"],
        style="minimal",
        extras="额外要求",
        video_img_urls=None,
        segment=[
            TranscriptSegment(start=1.5, end=2.5, text="第一段"),
            {"start": 3, "end": 4, "text": "第二段"},
        ],
    )
    gpt = UniversalGPT(client=Mock(), model="demo-model", temperature=0.2)
    gpt.max_request_bytes = 1234

    assert gpt._build_source_signature(source) == build_source_signature(
        source,
        model="demo-model",
        temperature=0.2,
        max_request_bytes=1234,
    )
