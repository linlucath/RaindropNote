import json
from typing import Any, Optional

from app.db.engine import get_db
from app.db.models.favorites import FavoriteTranscript
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _serialize_favorite(record: FavoriteTranscript) -> dict[str, Any]:
    transcript = None
    audio_meta = None

    if record.transcript_json:
        transcript = json.loads(record.transcript_json)
    if record.audio_meta_json:
        audio_meta = json.loads(record.audio_meta_json)

    return {
        "id": record.id,
        "source_task_id": record.source_task_id,
        "video_id": record.video_id,
        "platform": record.platform,
        "title": record.title,
        "markdown": record.markdown,
        "transcript": transcript,
        "audio_meta": audio_meta,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def upsert_favorite(
    *,
    source_task_id: str,
    title: str,
    video_id: Optional[str],
    platform: Optional[str],
    markdown: str,
    transcript: Optional[dict[str, Any]],
    audio_meta: Optional[dict[str, Any]],
) -> dict[str, Any]:
    db = next(get_db())
    try:
        record = (
            db.query(FavoriteTranscript)
            .filter_by(source_task_id=source_task_id)
            .first()
        )
        if record is None:
            record = FavoriteTranscript(source_task_id=source_task_id)
            db.add(record)

        record.title = title
        record.video_id = video_id
        record.platform = platform
        record.markdown = markdown
        record.transcript_json = (
            json.dumps(transcript, ensure_ascii=False) if transcript is not None else None
        )
        record.audio_meta_json = (
            json.dumps(audio_meta, ensure_ascii=False) if audio_meta is not None else None
        )
        db.commit()
        db.refresh(record)
        return _serialize_favorite(record)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to upsert favorite transcript: %s", exc)
        raise
    finally:
        db.close()


def list_favorites() -> list[dict[str, Any]]:
    db = next(get_db())
    try:
        records = (
            db.query(FavoriteTranscript)
            .order_by(FavoriteTranscript.updated_at.desc(), FavoriteTranscript.id.desc())
            .all()
        )
        return [_serialize_favorite(record) for record in records]
    finally:
        db.close()


def get_favorite_by_id(favorite_id: int) -> Optional[dict[str, Any]]:
    db = next(get_db())
    try:
        record = db.query(FavoriteTranscript).filter_by(id=favorite_id).first()
        return _serialize_favorite(record) if record else None
    finally:
        db.close()


def get_favorite_by_source_task_id(source_task_id: str) -> Optional[dict[str, Any]]:
    db = next(get_db())
    try:
        record = (
            db.query(FavoriteTranscript)
            .filter_by(source_task_id=source_task_id)
            .first()
        )
        return _serialize_favorite(record) if record else None
    finally:
        db.close()


def delete_favorite_by_id(favorite_id: int) -> int:
    db = next(get_db())
    try:
        record = db.query(FavoriteTranscript).filter_by(id=favorite_id).first()
        if record is None:
            return 0
        db.delete(record)
        db.commit()
        return 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
