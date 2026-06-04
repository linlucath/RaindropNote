from app.gpt.base import GPT
from app.gpt.prompt_builder import generate_base_prompt
from app.models.gpt_model import GPTSource
import os
import json
import time
from pathlib import Path

try:
    from app.gpt.checkpoint_store import (
        checkpoint_path,
        clear_checkpoint,
        load_checkpoint,
        save_checkpoint,
    )
except ModuleNotFoundError:  # pragma: no cover - supports isolated import tests
    import importlib.util
    import sys

    checkpoint_store_path = Path(__file__).with_name("checkpoint_store.py")
    spec = importlib.util.spec_from_file_location("_universal_gpt_checkpoint_store", checkpoint_store_path)
    if spec is None or spec.loader is None:
        raise
    checkpoint_store = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = checkpoint_store
    spec.loader.exec_module(checkpoint_store)
    checkpoint_path = checkpoint_store.checkpoint_path
    clear_checkpoint = checkpoint_store.clear_checkpoint
    load_checkpoint = checkpoint_store.load_checkpoint
    save_checkpoint = checkpoint_store.save_checkpoint

try:
    from app.gpt.retry_policy import is_retryable_error, retry_backoff_seconds
except ModuleNotFoundError:  # pragma: no cover - supports isolated import tests
    import importlib.util
    import sys

    retry_policy_path = Path(__file__).with_name("retry_policy.py")
    spec = importlib.util.spec_from_file_location("_universal_gpt_retry_policy", retry_policy_path)
    if spec is None or spec.loader is None:
        raise
    retry_policy = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = retry_policy
    spec.loader.exec_module(retry_policy)
    is_retryable_error = retry_policy.is_retryable_error
    retry_backoff_seconds = retry_policy.retry_backoff_seconds

try:
    from app.gpt.llm_cache import LlmCache, default_llm_cache_dir, default_llm_cache_enabled
except ModuleNotFoundError:  # pragma: no cover - supports isolated import tests
    import importlib.util
    import sys

    llm_cache_path = Path(__file__).with_name("llm_cache.py")
    spec = importlib.util.spec_from_file_location("_universal_gpt_llm_cache", llm_cache_path)
    if spec is None or spec.loader is None:
        raise
    llm_cache_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = llm_cache_module
    spec.loader.exec_module(llm_cache_module)
    LlmCache = llm_cache_module.LlmCache
    default_llm_cache_dir = llm_cache_module.default_llm_cache_dir
    default_llm_cache_enabled = llm_cache_module.default_llm_cache_enabled

try:
    from app.gpt import polished_transcript
except (ModuleNotFoundError, ImportError):  # pragma: no cover - supports isolated import tests
    import importlib.util
    import sys

    polished_transcript_path = Path(__file__).with_name("polished_transcript.py")
    spec = importlib.util.spec_from_file_location("_universal_gpt_polished_transcript", polished_transcript_path)
    if spec is None or spec.loader is None:
        raise
    polished_transcript = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = polished_transcript
    spec.loader.exec_module(polished_transcript)

try:
    from app.gpt import message_payloads
except (ModuleNotFoundError, ImportError):  # pragma: no cover - supports isolated import tests
    import importlib.util
    import sys

    message_payloads_path = Path(__file__).with_name("message_payloads.py")
    spec = importlib.util.spec_from_file_location("_universal_gpt_message_payloads", message_payloads_path)
    if spec is None or spec.loader is None:
        raise
    message_payloads = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = message_payloads
    spec.loader.exec_module(message_payloads)

try:
    from app.gpt import source_signature
except (ModuleNotFoundError, ImportError):  # pragma: no cover - supports isolated import tests
    import importlib.util
    import sys

    source_signature_path = Path(__file__).with_name("source_signature.py")
    spec = importlib.util.spec_from_file_location("_universal_gpt_source_signature", source_signature_path)
    if spec is None or spec.loader is None:
        raise
    source_signature = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = source_signature
    spec.loader.exec_module(source_signature)

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
try:
    from app.utils.logger import get_logger
except ModuleNotFoundError:  # pragma: no cover - supports isolated import tests
    import logging

    def get_logger(name: str):
        return logging.getLogger(name)
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = get_logger(__name__)


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
        self.llm_cache_enabled = default_llm_cache_enabled()
        self.llm_cache_dir = default_llm_cache_dir()
        # 初始化时缓存重试配置，避免每次请求重复读取环境变量
        self._max_retry_attempts = max(1, int(os.getenv("OPENAI_RETRY_ATTEMPTS", "3")))
        self._retry_base_backoff = float(os.getenv("OPENAI_RETRY_BACKOFF_SECONDS", "1.5"))

    def _llm_cache_helper(self) -> LlmCache:
        return LlmCache(
            client=self.client,
            model=self.model,
            temperature=self.temperature,
            cache_dir=self.llm_cache_dir,
            enabled=self.llm_cache_enabled,
        )

    @staticmethod
    def _build_cached_response(content: str):
        return LlmCache.build_cached_response(content)

    def _cache_provider_base_url(self) -> str | None:
        return self._llm_cache_helper().provider_base_url()

    def _llm_cache_key(self, messages: list) -> str:
        return self._llm_cache_helper().cache_key(messages)

    def _llm_cache_path(self, cache_key: str) -> Path:
        return self._llm_cache_helper().path(cache_key)

    @staticmethod
    def _cache_key_preview(cache_key: str) -> str:
        return LlmCache.key_preview(cache_key)

    def _summarize_messages(self, messages: list) -> str:
        return message_payloads.summarize_messages(messages)

    def _load_llm_cache(self, cache_key: str):
        return self._llm_cache_helper().load(cache_key)

    def _save_llm_cache(self, cache_key: str, content: str) -> None:
        self._llm_cache_helper().save(cache_key, content)

    def _format_time(self, seconds: float) -> str:
        return message_payloads.format_time(seconds)

    def _build_segment_text(self, segments: List[TranscriptSegment]) -> str:
        return message_payloads.build_segment_text(segments, self._format_time)

    def ensure_segments_type(self, segments) -> List[TranscriptSegment]:
        return [TranscriptSegment(**seg) if isinstance(seg, dict) else seg for seg in segments]

    def create_messages(self, segments: List[TranscriptSegment], **kwargs):

        return message_payloads.build_note_messages(
            segment_text=self._build_segment_text(segments),
            title=kwargs.get('title'),
            tags=kwargs.get('tags'),
            _format=kwargs.get('_format'),
            style=kwargs.get('style'),
            extras=kwargs.get('extras'),
            video_img_urls=kwargs.get('video_img_urls', []),
            generate_prompt=generate_base_prompt,
        )

    def list_models(self):
        return self.client.models.list()

    def _estimate_messages_bytes(self, messages: list) -> int:
        import json
        return len(json.dumps(messages, ensure_ascii=False).encode("utf-8"))

    def _build_merge_messages(self, partials: list) -> list:
        return message_payloads.build_merge_messages(partials, MERGE_PROMPT)

    def _build_polished_transcript_messages(self, segments: List[TranscriptSegment], **kwargs) -> list:
        section_guidance = self._polished_transcript_section_guidance(segments)
        language_guidance = self._polished_transcript_language_guidance(
            kwargs.get("language"),
            segments,
        )
        return message_payloads.build_polished_transcript_messages(
            segment_text=self._build_segment_text(segments),
            title=kwargs.get("title"),
            tags=kwargs.get("tags"),
            section_guidance=section_guidance,
            language_guidance=language_guidance,
            prompt_template=POLISHED_TRANSCRIPT_PROMPT,
        )

    def _build_polished_transcript_chunk_messages(self, segments: List[TranscriptSegment], **kwargs) -> list:
        return message_payloads.build_polished_transcript_chunk_messages(
            segment_text=self._build_segment_text(segments),
            title=kwargs.get("title"),
            tags=kwargs.get("tags"),
            language_guidance=self._polished_transcript_language_guidance(
                kwargs.get("language"),
                segments,
            ),
            prompt_template=POLISHED_TRANSCRIPT_CHUNK_PROMPT,
        )

    def _build_polished_transcript_merge_messages(self, partials: list, language: str | None = None) -> list:
        return message_payloads.build_polished_transcript_merge_messages(
            partials,
            self._polished_transcript_language_guidance(language, []),
            POLISHED_TRANSCRIPT_MERGE_PROMPT,
        )

    def _build_polished_transcript_repair_messages(
        self,
        segments: List[TranscriptSegment],
        draft_text: str,
        **kwargs,
    ) -> list:
        return message_payloads.build_polished_transcript_repair_messages(
            segment_text=self._build_segment_text(segments),
            title=kwargs.get("title"),
            tags=kwargs.get("tags"),
            draft_text=draft_text,
            language_guidance=self._polished_transcript_language_guidance(
                kwargs.get("language"),
                segments,
            ),
            prompt_template=POLISHED_TRANSCRIPT_REPAIR_PROMPT,
        )

    def _checkpoint_path(self, checkpoint_key: str) -> Path:
        return checkpoint_path(self.checkpoint_dir, checkpoint_key)

    def _build_source_signature(self, source: GPTSource) -> str:
        return source_signature.build_source_signature(
            source,
            model=self.model,
            temperature=self.temperature,
            max_request_bytes=self.max_request_bytes,
        )

    def _polished_transcript_section_guidance(self, segments: List[TranscriptSegment]) -> str:
        return polished_transcript.polished_transcript_section_guidance(segments)

    @staticmethod
    def _polished_transcript_language_guidance(language: str | None, segments: List[TranscriptSegment]) -> str:
        return polished_transcript.polished_transcript_language_guidance(language, segments)

    @staticmethod
    def _strip_markdown_for_length(text: str) -> str:
        return polished_transcript.strip_markdown_for_length(text)

    def _source_text_length(self, segments: List[TranscriptSegment]) -> int:
        return polished_transcript.source_text_length(segments)

    def _needs_polished_transcript_repair(self, segments: List[TranscriptSegment], draft_text: str) -> bool:
        return polished_transcript.needs_polished_transcript_repair(segments, draft_text)

    def _repair_polished_transcript(self, source: GPTSource, draft_text: str) -> str:
        messages = self._build_polished_transcript_repair_messages(
            source.segment,
            draft_text,
            title=source.title,
            tags=source.tags,
            language=source.language,
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
        def message_builder(group_segments, _image_urls=None, **kwargs):
            return self._build_polished_transcript_chunk_messages(group_segments, **kwargs)

        byte_chunker = RequestChunker(message_builder, self.max_request_bytes, self._estimate_messages_bytes)
        return polished_transcript.split_polished_transcript_segments(
            segments,
            self.polished_transcript_max_source_chars,
            byte_chunker,
            title=title,
            tags=tags,
        )

    def _repair_polished_transcript_segments(
        self,
        segments: List[TranscriptSegment],
        draft_text: str,
        title: str,
        tags,
        language: str | None,
    ) -> str:
        messages = self._build_polished_transcript_repair_messages(
            segments,
            draft_text,
            title=title,
            tags=tags,
            language=language,
        )
        response = self._chat_completion_create(messages)
        repaired = (response.choices[0].message.content or "").strip()
        return repaired or draft_text

    def _polish_transcript_chunk(self, chunk, title: str, tags, language: str | None) -> str:
        messages = self._build_polished_transcript_chunk_messages(
            chunk.segments,
            title=title,
            tags=tags,
            language=language,
        )
        response = self._chat_completion_create(messages)
        draft = (response.choices[0].message.content or "").strip()
        if draft and self._needs_polished_transcript_repair(chunk.segments, draft):
            return self._repair_polished_transcript_segments(
                chunk.segments,
                draft,
                title,
                tags,
                language,
            )
        return draft

    @staticmethod
    def _stitch_polished_transcript_partials(partials: List[str]) -> str:
        return polished_transcript.stitch_polished_transcript_partials(partials)

    def _load_checkpoint(self, checkpoint_key: str, source_signature: str) -> dict | None:
        return load_checkpoint(self.checkpoint_dir, checkpoint_key, source_signature)

    def _save_checkpoint(self, checkpoint_key: str, source_signature: str, partials: list, phase: str) -> None:
        save_checkpoint(self.checkpoint_dir, checkpoint_key, source_signature, partials, phase)

    def _clear_checkpoint(self, checkpoint_key: str) -> None:
        clear_checkpoint(self.checkpoint_dir, checkpoint_key)

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
        return is_retryable_error(exc)

    def _chat_completion_create(self, messages: list):
        cache_key = self._llm_cache_key(messages)
        logger.info(
            "LLM request start: key=%s model=%s provider=%s temperature=%s cache_enabled=%s approx_bytes=%d messages=%s",
            self._cache_key_preview(cache_key),
            self.model,
            self._cache_provider_base_url(),
            self.temperature,
            self.llm_cache_enabled,
            self._estimate_messages_bytes(messages),
            self._summarize_messages(messages),
        )
        cached_response = self._load_llm_cache(cache_key)
        if cached_response is not None:
            return cached_response

        last_exc = None
        for attempt in range(self._max_retry_attempts):
            try:
                logger.info(
                    "LLM provider request: key=%s attempt=%d/%d",
                    self._cache_key_preview(cache_key),
                    attempt + 1,
                    self._max_retry_attempts,
                )
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature
                )
                content = response.choices[0].message.content or ""
                logger.info(
                    "LLM provider response: key=%s attempt=%d content_chars=%d",
                    self._cache_key_preview(cache_key),
                    attempt + 1,
                    len(content),
                )
                self._save_llm_cache(cache_key, content)
                return response
            except Exception as exc:
                last_exc = exc
                if attempt == self._max_retry_attempts - 1 or not self._is_retryable_error(exc):
                    logger.error(
                        "LLM provider failed: key=%s attempt=%d/%d retryable=%s error=%s",
                        self._cache_key_preview(cache_key),
                        attempt + 1,
                        self._max_retry_attempts,
                        self._is_retryable_error(exc),
                        exc,
                    )
                    raise
                sleep_seconds = retry_backoff_seconds(self._retry_base_backoff, attempt)
                logger.warning(
                    "LLM provider retrying: key=%s attempt=%d/%d backoff_seconds=%.2f error=%s",
                    self._cache_key_preview(cache_key),
                    attempt + 1,
                    self._max_retry_attempts,
                    sleep_seconds,
                    exc,
                )
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
                executor.submit(
                    self._polish_transcript_chunk,
                    chunk,
                    source.title,
                    source.tags,
                    source.language,
                ): idx
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
