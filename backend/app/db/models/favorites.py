from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.db.engine import Base


class FavoriteTranscript(Base):
    __tablename__ = "favorite_transcripts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_task_id = Column(String, unique=True, nullable=False, index=True)
    video_id = Column(String, nullable=True)
    platform = Column(String, nullable=True)
    title = Column(String, nullable=False)
    markdown = Column(Text, nullable=False)
    transcript_json = Column(Text, nullable=True)
    audio_meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
