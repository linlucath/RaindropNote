from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Callable

import httpx
from fastapi import HTTPException, UploadFile


DEFAULT_UPLOAD_DIR = Path("uploads")
DEFAULT_UPLOAD_PUBLIC_PREFIX = "/uploads"
IMAGE_PROXY_REFERER = "https://www.bilibili.com/"
IMAGE_PROXY_TIMEOUT = 10.0
IMAGE_PROXY_CACHE_CONTROL = "public, max-age=86400"


@dataclass(frozen=True)
class UploadedAsset:
    path: Path
    url: str


@dataclass(frozen=True)
class ImageProxyResult:
    body: AsyncIterator[bytes]
    media_type: str
    headers: dict[str, str]


AsyncClientFactory = Callable[..., Any]


async def save_uploaded_file(
    file: UploadFile,
    upload_dir: str | Path = DEFAULT_UPLOAD_DIR,
    public_prefix: str = DEFAULT_UPLOAD_PUBLIC_PREFIX,
) -> UploadedAsset:
    target_dir = Path(upload_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_location = target_dir / file.filename

    with file_location.open("wb+") as f:
        f.write(await file.read())

    return UploadedAsset(path=file_location, url=f"{public_prefix}/{file.filename}")


def build_image_proxy_headers(user_agent: str) -> dict[str, str]:
    return {
        "Referer": IMAGE_PROXY_REFERER,
        "User-Agent": user_agent,
    }


async def fetch_image_proxy(
    url: str,
    user_agent: str,
    client_factory: AsyncClientFactory | None = None,
    timeout: float = IMAGE_PROXY_TIMEOUT,
) -> ImageProxyResult:
    headers = build_image_proxy_headers(user_agent)
    client_factory = client_factory or httpx.AsyncClient

    try:
        async with client_factory(timeout=timeout) as client:
            resp = await client.get(url, headers=headers)

            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="图片获取失败")

            content_type = resp.headers.get("Content-Type", "image/jpeg")
            return ImageProxyResult(
                body=resp.aiter_bytes(),
                media_type=content_type,
                headers={
                    "Cache-Control": IMAGE_PROXY_CACHE_CONTROL,
                    "Content-Type": content_type,
                },
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
