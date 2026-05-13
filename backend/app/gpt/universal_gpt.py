from app.gpt.base import GPT
from app.gpt.prompt_builder import generate_base_prompt
from app.models.gpt_model import GPTSource
import os
import hashlib
import json
import time
from types import SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path

from app.gpt.prompt import (
    BASE_PROMPT,
    AI_SUM,
    SCREENSHOT,
    LINK,
    MERGE_PROMPT,
    POLISHED_TRANSCRIPT_CHUNK_PROMPT,
    POLISHED_TRANSCRIPT_PROMPT,
    POLISHED_TRANSCRIPT_MERGE_PROMPT,
    POLISHED_TRANSCRIPT_REPAIR_PROMPT,
)
from app.gpt.utils import fix_markdown
from app.gpt.request_chunker import RequestChunker
from app.models.transcriber_model import TranscriptSegment
from datetime import timedelta
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed


class UniversalGPT(GPT):
    def __init__(self, client, model: str, temperature: float = 0.7):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.screenshot = False
        self.link = False
        self.max_request_bytes = int(os.getenv("OPENAI_MAX_REQUEST_BYTES", str(45 * 1024 * 1024)))
        self.polished_transcript_max_source_chars = int(os.getenv("POLISHED_TRANSCRIPT_MAX_SOURCE_CHARS", "4000"))
        self.checkpoint_dir = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results"))
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.llm_cache_enabled = os.getenv("LLM_CACHE_ENABLED", "1").lower() not in {"0", "false", "no"}
        self.llm_cache_dir = Path(
            os.getenv(
                "LLM_CACHE_DIR",
                str(Path(__file__).resolve().parents[3] / ".cache" / "llm"),
            )
        )
        # 初始化时缓存重试配置，避免每次请求重复读取环境变量
        self._max_retry_attempts = max(1, int(os.getenv("OPENAI_RETRY_ATTEMPTS", "3")))
        self._retry_base_backoff = float(os.getenv("OPENAI_RETRY_BACKOFF_SECONDS", "1.5"))

    @staticmethod
    def _build_cached_response(content: str):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            from_cache=True,
        )

    def _cache_provider_base_url(self) -> str | None:
        base_url = getattr(self.client, "base_url", None)
        if base_url is None and hasattr(self.client, "_base_url"):
            base_url = getattr(self.client, "_base_url")
        return str(base_url) if base_url else None

    def _llm_cache_key(self, messages: list) -> str:
        payload = {
            "version": 1,
            "provider_base_url": self._cache_provider_base_url(),
            "model": self.model,
            "temperature": self.temperature,
            "messages": messages,
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _llm_cache_path(self, cache_key: str) -> Path:
        return self.llm_cache_dir / f"{cache_key}.json"

    def _load_llm_cache(self, cache_key: str):
        if not self.llm_cache_enabled:
            return None

        path = self._llm_cache_path(cache_key)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            path.unlink(missing_ok=True)
            return None

        content = payload.get("content")
        if not isinstance(content, str):
            path.unlink(missing_ok=True)
            return None

        return self._build_cached_response(content)

    def _save_llm_cache(self, cache_key: str, content: str) -> None:
        if not self.llm_cache_enabled or not isinstance(content, str) or not content.strip():
            return

        self.llm_cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._llm_cache_path(cache_key)
        payload = {
            "version": 1,
            "provider_base_url": self._cache_provider_base_url(),
            "model": self.model,
            "temperature": self.temperature,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def _format_time(self, seconds: float) -> str:
        return str(timedelta(seconds=int(seconds)))[2:]

    def _build_segment_text(self, segments: List[TranscriptSegment]) -> str:
        return "\n".join(
            f"{self._format_time(seg.start)} - {seg.text.strip()}"
            for seg in segments
        )

    def ensure_segments_type(self, segments) -> List[TranscriptSegment]:
        return [TranscriptSegment(**seg) if isinstance(seg, dict) else seg for seg in segments]

    def create_messages(self, segments: List[TranscriptSegment], **kwargs):

        content_text = generate_base_prompt(
            title=kwargs.get('title'),
            segment_text=self._build_segment_text(segments),
            tags=kwargs.get('tags'),
            _format=kwargs.get('_format'),
            style=kwargs.get('style'),
            extras=kwargs.get('extras'),
        )

        # ⛳ 组装 content 数组，支持 text + image_url 混合
        content: List[dict] = [{"type": "text", "text": content_text}]
        video_img_urls = kwargs.get('video_img_urls', [])

        for url in video_img_urls:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": url,
                    "detail": "auto"
                }
            })

        #  正确格式：整体包在一个 message 里，role + content array
        messages = [{
            "role": "user",
            "content": content
        }]

        return messages

    def list_models(self):
        return self.client.models.list()

    def _estimate_messages_bytes(self, messages: list) -> int:
        import json
        return len(json.dumps(messages, ensure_ascii=False).encode("utf-8"))

    def _build_merge_messages(self, partials: list) -> list:
        merge_text = MERGE_PROMPT + "\n\n" + "\n\n---\n\n".join(partials)
        return [{
            "role": "user",
            "content": [{"type": "text", "text": merge_text}]
        }]

    def _build_polished_transcript_messages(self, segments: List[TranscriptSegment], **kwargs) -> list:
        section_guidance = self._polished_transcript_section_guidance(segments)
        prompt = POLISHED_TRANSCRIPT_PROMPT.format(
            video_title=kwargs.get("title"),
            segment_text=self._build_segment_text(segments),
            tags=kwargs.get("tags"),
            section_guidance=section_guidance,
        )
        return [{
            "role": "user",
            "content": [{"type": "text", "text": prompt}]
        }]

    def _build_polished_transcript_chunk_messages(self, segments: List[TranscriptSegment], **kwargs) -> list:
        prompt = POLISHED_TRANSCRIPT_CHUNK_PROMPT.format(
            video_title=kwargs.get("title"),
            segment_text=self._build_segment_text(segments),
            tags=kwargs.get("tags"),
        )
        return [{
            "role": "user",
            "content": [{"type": "text", "text": prompt}]
        }]

    def _build_polished_transcript_merge_messages(self, partials: list) -> list:
        merge_text = POLISHED_TRANSCRIPT_MERGE_PROMPT + "\n\n" + "\n\n---\n\n".join(partials)
        return [{
            "role": "user",
            "content": [{"type": "text", "text": merge_text}]
        }]

    def _build_polished_transcript_repair_messages(
        self,
        segments: List[TranscriptSegment],
        draft_text: str,
        **kwargs,
    ) -> list:
        prompt = POLISHED_TRANSCRIPT_REPAIR_PROMPT.format(
            video_title=kwargs.get("title"),
            segment_text=self._build_segment_text(segments),
            tags=kwargs.get("tags"),
            draft_text=draft_text,
        )
        return [{
            "role": "user",
            "content": [{"type": "text", "text": prompt}]
        }]

    def _checkpoint_path(self, checkpoint_key: str) -> Path:
        safe_key = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in checkpoint_key)
        return self.checkpoint_dir / f"{safe_key}.gpt.checkpoint.json"

    def _build_source_signature(self, source: GPTSource) -> str:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_request_bytes": self.max_request_bytes,
            "title": source.title,
            "tags": source.tags,
            "format": source._format,
            "style": source.style,
            "extras": source.extras,
            "video_img_urls": source.video_img_urls or [],
            "segments": [
                {
                    "start": getattr(seg, "start", None),
                    "end": getattr(seg, "end", None),
                    "text": getattr(seg, "text", "")
                }
                for seg in source.segment
            ],
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _polished_transcript_section_guidance(self, segments: List[TranscriptSegment]) -> str:
        text_length = sum(len((getattr(seg, "text", "") or "").strip()) for seg in segments)
        if text_length >= 12000:
            return "6-12 个 `##` 章节"
        if text_length >= 5000:
            return "4-8 个 `##` 章节"
        return "3-6 个 `##` 章节"

    @staticmethod
    def _strip_markdown_for_length(text: str) -> str:
        cleaned = text or ""
        replacements = (
            ("**", ""),
            ("### ", ""),
            ("## ", ""),
            ("# ", ""),
            ("`", ""),
            ("> ", ""),
            ("-", " "),
            ("*", ""),
        )
        for old, new in replacements:
            cleaned = cleaned.replace(old, new)
        return " ".join(cleaned.split())

    def _source_text_length(self, segments: List[TranscriptSegment]) -> int:
        return sum(len((getattr(seg, "text", "") or "").strip()) for seg in segments)

    def _needs_polished_transcript_repair(self, segments: List[TranscriptSegment], draft_text: str) -> bool:
        source_length = self._source_text_length(segments)
        if source_length <= 0:
            return False

        output_length = len(self._strip_markdown_for_length(draft_text))
        ratio = output_length / source_length
        threshold = 0.72 if source_length < 12000 else 0.82
        return ratio < threshold

    def _repair_polished_transcript(self, source: GPTSource, draft_text: str) -> str:
        messages = self._build_polished_transcript_repair_messages(
            source.segment,
            draft_text,
            title=source.title,
            tags=source.tags,
        )
        response = self._chat_completion_create(messages)
        repaired = (response.choices[0].message.content or "").strip()
        return repaired or draft_text

    def _polished_transcript_max_workers(self) -> int:
        workers = int(os.getenv("POLISHED_TRANSCRIPT_MAX_WORKERS", "3"))
        return max(1, min(workers, 8))

    def _split_polished_transcript_segments(
        self,
        segments: List[TranscriptSegment],
        title: str,
        tags,
    ):
        budget = max(500, self.polished_transcript_max_source_chars)
        coarse_groups: List[List[TranscriptSegment]] = []
        current_group: List[TranscriptSegment] = []
        current_chars = 0

        for segment in segments:
            segment_text = (getattr(segment, "text", "") or "").strip()
            segment_chars = len(segment_text)

            if current_group and current_chars + segment_chars > budget:
                coarse_groups.append(current_group)
                current_group = []
                current_chars = 0

            current_group.append(segment)
            current_chars += segment_chars

        if current_group:
            coarse_groups.append(current_group)

        def message_builder(group_segments, _image_urls=None, **kwargs):
            return self._build_polished_transcript_chunk_messages(group_segments, **kwargs)

        byte_chunker = RequestChunker(message_builder, self.max_request_bytes, self._estimate_messages_bytes)
        chunks = []
        for group in coarse_groups:
            chunks.extend(byte_chunker.chunk(group, [], title=title, tags=tags))
        return chunks

    def _repair_polished_transcript_segments(self, segments: List[TranscriptSegment], draft_text: str, title: str, tags) -> str:
        messages = self._build_polished_transcript_repair_messages(
            segments,
            draft_text,
            title=title,
            tags=tags,
        )
        response = self._chat_completion_create(messages)
        repaired = (response.choices[0].message.content or "").strip()
        return repaired or draft_text

    def _polish_transcript_chunk(self, chunk, title: str, tags) -> str:
        messages = self._build_polished_transcript_chunk_messages(
            chunk.segments,
            title=title,
            tags=tags,
        )
        response = self._chat_completion_create(messages)
        draft = (response.choices[0].message.content or "").strip()
        if draft and self._needs_polished_transcript_repair(chunk.segments, draft):
            return self._repair_polished_transcript_segments(chunk.segments, draft, title, tags)
        return draft

    @staticmethod
    def _stitch_polished_transcript_partials(partials: List[str]) -> str:
        cleaned = [part.strip() for part in partials if part and part.strip()]
        if not cleaned:
            return ""
        stitched = "\n\n".join(cleaned)
        stitched = stitched.replace("\r\n", "\n")
        while "\n\n\n" in stitched:
            stitched = stitched.replace("\n\n\n", "\n\n")
        return stitched.strip()

    def _load_checkpoint(self, checkpoint_key: str, source_signature: str) -> dict | None:
        path = self._checkpoint_path(checkpoint_key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("source_signature") != source_signature:
                path.unlink(missing_ok=True)
                return None
            return data
        except Exception:
            path.unlink(missing_ok=True)
            return None

    def _save_checkpoint(self, checkpoint_key: str, source_signature: str, partials: list, phase: str) -> None:
        path = self._checkpoint_path(checkpoint_key)
        data = {
            "version": 1,
            "source_signature": source_signature,
            "phase": phase,
            "partials": partials,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def _clear_checkpoint(self, checkpoint_key: str) -> None:
        self._checkpoint_path(checkpoint_key).unlink(missing_ok=True)

    @staticmethod
    def _is_insufficient_quota_error(exc: Exception) -> bool:
        raw = str(exc)
        return (
            "insufficient_user_quota" in raw
            or "预扣费额度失败" in raw
            or "insufficient quota" in raw.lower()
        )

    @staticmethod
    def _is_retryable_error(exc: Exception) -> bool:
        raw = str(exc).lower()
        retryable_tokens = (
            "error code: 524",
            "bad_response_status_code",
            "timed out",
            "timeout",
            "rate limit",
            "error code: 429",
            "error code: 500",
            "error code: 502",
            "error code: 503",
            "error code: 504",
            "apiconnectionerror",
            "connection error",
            "service unavailable",
        )
        if any(token in raw for token in retryable_tokens):
            return True

        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        return status in {408, 409, 429, 500, 502, 503, 504, 524}

    def _chat_completion_create(self, messages: list):
        cache_key = self._llm_cache_key(messages)
        cached_response = self._load_llm_cache(cache_key)
        if cached_response is not None:
            return cached_response

        last_exc = None
        for attempt in range(self._max_retry_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature
                )
                content = response.choices[0].message.content or ""
                self._save_llm_cache(cache_key, content)
                return response
            except Exception as exc:
                last_exc = exc
                if attempt == self._max_retry_attempts - 1 or not self._is_retryable_error(exc):
                    raise
                sleep_seconds = self._retry_base_backoff * (2 ** attempt)
                time.sleep(sleep_seconds)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("chat completion failed without exception")

    def _merge_partials(self, partials: list, checkpoint_key: str | None, source_signature: str | None) -> str:
        def build_messages(texts, *_args, **_kwargs):
            return self._build_merge_messages(texts)

        merge_chunker = RequestChunker(
            lambda *_args, **_kwargs: [],
            self.max_request_bytes,
            self._estimate_messages_bytes
        )

        current_partials = list(partials)
        while len(current_partials) > 1:
            groups = merge_chunker.group_texts_by_budget(current_partials, build_messages)
            new_partials = []
            for group_idx, group in enumerate(groups):
                messages = build_messages(group)
                try:
                    response = self._chat_completion_create(messages)
                except Exception as exc:
                    if checkpoint_key and source_signature:
                        self._save_checkpoint(checkpoint_key, source_signature, current_partials, "merge")
                    raise

                new_partials.append(response.choices[0].message.content.strip())

                if checkpoint_key and source_signature:
                    remaining_partials = []
                    for remaining_group in groups[group_idx + 1:]:
                        remaining_partials.extend(remaining_group)
                    resumable_partials = new_partials + remaining_partials
                    self._save_checkpoint(checkpoint_key, source_signature, resumable_partials, "merge")

            current_partials = new_partials

        return current_partials[0]

    def summarize(self, source: GPTSource) -> str:
        self.screenshot = source.screenshot
        self.link = source.link
        source.segment = self.ensure_segments_type(source.segment)
        checkpoint_key = source.checkpoint_key
        source_signature = self._build_source_signature(source) if checkpoint_key else None

        def message_builder(segments, image_urls, **kwargs):
            return self.create_messages(segments, video_img_urls=image_urls, **kwargs)

        chunker = RequestChunker(message_builder, self.max_request_bytes, self._estimate_messages_bytes)

        try:
            chunks = chunker.chunk(
                source.segment,
                source.video_img_urls or [],
                title=source.title,
                tags=source.tags,
                _format=source._format,
                style=source.style,
                extras=source.extras
            )
        except ValueError:
            chunks = chunker.chunk(
                source.segment,
                [],
                title=source.title,
                tags=source.tags,
                _format=source._format,
                style=source.style,
                extras=source.extras
            )

        partials = []
        if checkpoint_key and source_signature:
            checkpoint = self._load_checkpoint(checkpoint_key, source_signature)
            if checkpoint and isinstance(checkpoint.get("partials"), list):
                partials = checkpoint["partials"]

        if len(partials) > len(chunks):
            partials = []

        for chunk in chunks[len(partials):]:
            messages = self.create_messages(
                chunk.segments,
                title=source.title,
                tags=source.tags,
                video_img_urls=chunk.image_urls,
                _format=source._format,
                style=source.style,
                extras=source.extras
            )
            try:
                response = self._chat_completion_create(messages)
            except Exception as exc:
                if checkpoint_key and source_signature:
                    self._save_checkpoint(checkpoint_key, source_signature, partials, "summarize")
                raise

            partials.append(response.choices[0].message.content.strip())
            if checkpoint_key and source_signature:
                self._save_checkpoint(checkpoint_key, source_signature, partials, "summarize")

        if len(partials) == 1:
            if checkpoint_key:
                self._clear_checkpoint(checkpoint_key)
            return partials[0]
        merged = self._merge_partials(partials, checkpoint_key, source_signature)
        if checkpoint_key:
            self._clear_checkpoint(checkpoint_key)
        return merged

    def polish_transcript(self, source: GPTSource) -> str:
        source.segment = self.ensure_segments_type(source.segment)
        chunks = self._split_polished_transcript_segments(
            source.segment,
            title=source.title,
            tags=source.tags,
        )

        partials = [""] * len(chunks)
        max_workers = min(self._polished_transcript_max_workers(), max(1, len(chunks)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._polish_transcript_chunk, chunk, source.title, source.tags): idx
                for idx, chunk in enumerate(chunks)
            }
            for future in as_completed(futures):
                partials[futures[future]] = future.result()

        partials = [part for part in partials if part]
        if len(partials) <= 1:
            result = partials[0] if partials else ""
            if result and self._needs_polished_transcript_repair(source.segment, result):
                return self._repair_polished_transcript(source, result)
            return result

        result = self._stitch_polished_transcript_partials(partials)
        return result
