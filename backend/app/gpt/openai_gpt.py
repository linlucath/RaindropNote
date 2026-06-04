import logging
from typing import List

from app.gpt.base import GPT
from app.gpt.legacy_messages import (
    build_legacy_prompt_messages,
    build_segment_text,
    ensure_segments_type,
    format_time,
)
from app.gpt.provider.OpenAI_compatible_provider import OpenAICompatibleProvider
from app.models.gpt_model import GPTSource
from app.models.transcriber_model import TranscriptSegment

logger = logging.getLogger(__name__)


class OpenaiGPT(GPT):
    def __init__(self):
        from os import getenv
        self.api_key = getenv("OPENAI_API_KEY")
        self.base_url = getenv("OPENAI_API_BASE_URL")
        self.model=getenv('OPENAI_MODEL')
        logger.debug("OpenAI model: %s", self.model)
        self.client = OpenAICompatibleProvider(api_key=self.api_key, base_url=self.base_url)
        self.screenshot = False
        self.link=False

    def _format_time(self, seconds: float) -> str:
        return format_time(seconds)

    def _build_segment_text(self, segments: List[TranscriptSegment]) -> str:
        return build_segment_text(segments)

    def ensure_segments_type(self, segments) -> List[TranscriptSegment]:
        return ensure_segments_type(segments)

    def create_messages(self, segments: List[TranscriptSegment], title: str,tags:str):
        messages = build_legacy_prompt_messages(
            segments,
            title=title,
            tags=tags,
            include_screenshot=self.screenshot,
            include_link=self.link,
        )
        if self.screenshot:
            logger.debug(":需要截图")
        if self.link:
            logger.debug(":需要链接")
        logger.debug(messages[0]["content"])
        return messages
    def list_models(self):
        return self.client.list_models()
    def summarize(self, source: GPTSource) -> str:
        self.screenshot = source.screenshot
        self.link = source.link
        source.segment = self.ensure_segments_type(source.segment)
        messages = self.create_messages(source.segment, source.title,source.tags)
        response = self.client.chat(
            model=self.model,
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()

if __name__ == '__main__':
    gpt = OpenaiGPT()
    print(gpt.list_models())
