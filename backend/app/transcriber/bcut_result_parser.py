import json

from app.models.transcriber_model import TranscriptSegment, TranscriptResult


def parse_task_result(task_result: str) -> TranscriptResult:
    result_json = json.loads(task_result)

    segments = []
    full_text = ""

    for utterance in result_json.get("utterances", []):
        text = utterance.get("transcript", "").strip()
        start_time = float(utterance.get("start_time", 0)) / 1000.0
        end_time = float(utterance.get("end_time", 0)) / 1000.0

        full_text += text + " "
        segments.append(TranscriptSegment(
            start=start_time,
            end=end_time,
            text=text
        ))

    return TranscriptResult(
        language=result_json.get("language", "zh"),
        full_text=full_text.strip(),
        segments=segments,
        raw=result_json
    )
