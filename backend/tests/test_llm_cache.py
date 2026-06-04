import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.gpt.llm_cache import LlmCache
from app.gpt.universal_gpt import UniversalGPT


def _response_with_content(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
    )


class _FakeCompletions:
    def __init__(self, content: str):
        self.content = content
        self.calls = 0

    def create(self, **_kwargs):
        self.calls += 1
        return _response_with_content(self.content)


class _FakeClient:
    def __init__(self, content: str, base_url: str = 'https://example.com/v1'):
        self.base_url = base_url
        self.chat = SimpleNamespace(completions=_FakeCompletions(content))
        self.models = SimpleNamespace(list=lambda: [])


class TestLlmCache(unittest.TestCase):
    def test_helper_can_save_and_load_cached_response_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = _FakeClient('unused')
            cache = LlmCache(
                client=client,
                model='demo-model',
                temperature=0.7,
                cache_dir=Path(tmp) / '.cache' / 'llm',
                enabled=True,
            )
            messages = [{'role': 'user', 'content': [{'type': 'text', 'text': 'hello'}]}]
            cache_key = cache.cache_key(messages)

            cache.save(cache_key, 'cached answer')
            response = cache.load(cache_key)

            cache_files = list(cache.cache_dir.glob('*.json'))
            payload = json.loads(cache_files[0].read_text(encoding='utf-8'))

        self.assertEqual(response.choices[0].message.content, 'cached answer')
        self.assertTrue(getattr(response, 'from_cache', False))
        self.assertEqual(len(cache_files), 1)
        self.assertEqual(payload['provider_base_url'], 'https://example.com/v1')
        self.assertEqual(payload['model'], 'demo-model')
        self.assertEqual(payload['temperature'], 0.7)
        self.assertEqual(payload['content'], 'cached answer')

    def test_chat_completion_uses_persistent_disk_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = _FakeClient('cached answer')
            gpt = UniversalGPT(client=client, model='demo-model')
            gpt.llm_cache_dir = Path(tmp) / '.cache' / 'llm'
            messages = [{'role': 'user', 'content': [{'type': 'text', 'text': 'hello'}]}]

            first = gpt._chat_completion_create(messages)
            second = gpt._chat_completion_create(messages)

            cache_files = list(gpt.llm_cache_dir.glob('*.json'))
            payload = json.loads(cache_files[0].read_text(encoding='utf-8'))

        self.assertEqual(client.chat.completions.calls, 1)
        self.assertEqual(first.choices[0].message.content, 'cached answer')
        self.assertEqual(second.choices[0].message.content, 'cached answer')
        self.assertFalse(getattr(first, 'from_cache', False))
        self.assertTrue(getattr(second, 'from_cache', False))
        self.assertEqual(len(cache_files), 1)
        self.assertEqual(payload['model'], 'demo-model')
        self.assertEqual(payload['content'], 'cached answer')

    def test_different_messages_use_different_cache_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = _FakeClient('answer')
            gpt = UniversalGPT(client=client, model='demo-model')
            gpt.llm_cache_dir = Path(tmp) / '.cache' / 'llm'

            gpt._chat_completion_create([{'role': 'user', 'content': [{'type': 'text', 'text': 'hello'}]}])
            gpt._chat_completion_create([{'role': 'user', 'content': [{'type': 'text', 'text': 'world'}]}])

        self.assertEqual(client.chat.completions.calls, 2)

    def test_empty_content_is_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = _FakeClient('')
            gpt = UniversalGPT(client=client, model='demo-model')
            gpt.llm_cache_dir = Path(tmp) / '.cache' / 'llm'
            messages = [{'role': 'user', 'content': [{'type': 'text', 'text': 'hello'}]}]

            gpt._chat_completion_create(messages)
            gpt._chat_completion_create(messages)

        self.assertEqual(client.chat.completions.calls, 2)
        self.assertFalse(gpt.llm_cache_dir.exists())


if __name__ == '__main__':
    unittest.main()
