from typing import Optional

from pydantic import BaseModel, Field

from app.enmus.note_enums import DownloadQuality
from app.services.task_runtime import SUPPORTED_GENERATION_MODE


class BatchPreviewRequest(BaseModel):
    space_url: str
    limit: int = Field(default=0, ge=0, le=500)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)


class BatchVideo(BaseModel):
    video_id: str
    video_url: str
    title: str = ""
    platform: Optional[str] = None


class BatchStartRequest(BaseModel):
    videos: list[BatchVideo]
    mode: str = SUPPORTED_GENERATION_MODE
    quality: DownloadQuality = DownloadQuality.fast
    skip_existing: bool = True
    concurrency: int = Field(default=1, ge=1, le=2)
    link: bool = False
    screenshot: bool = False
    model_name: Optional[str] = None
    provider_id: Optional[str] = None
    format: list[str] = Field(default_factory=list)
    style: Optional[str] = None
    extras: Optional[str] = None
    video_understanding: bool = False
    video_interval: int = 0
    grid_size: list[int] = Field(default_factory=list)


class BatchCancelRequest(BaseModel):
    batch_id: str
