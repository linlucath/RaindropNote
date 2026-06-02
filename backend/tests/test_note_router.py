import unittest
import json
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import HTTPException
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from app.enmus.note_enums import DownloadQuality
from app.models.notes_model import NoteResult
from app.routers import note as note_router
from app.routers.note import run_note_task


class TestNoteRouter(unittest.TestCase):
    def test_default_transcript_task_requires_model_before_generation(self):
        fake_note = NoteResult(markdown="# 标题\n\n## 简体中文文字稿\n\n已有字幕", transcript=None, audio_meta=None)

        with patch("app.routers.note.NoteGenerator") as generator_cls, patch(
            "app.routers.note.save_note_to_file"
        ), patch("app.routers.note.get_task_executor") as get_task_executor:
            get_task_executor.return_value.run.side_effect = lambda fn: fn()
            generator_cls.return_value.generate = Mock(return_value=fake_note)

            with self.assertRaises(HTTPException) as ctx:
                run_note_task(
                    task_id="subtitle-polished-task",
                    video_url="https://www.bilibili.com/video/BV123",
                    platform="bilibili",
                    quality=DownloadQuality.fast,
                )

        self.assertEqual(ctx.exception.status_code, 400)
        generator_cls.return_value.generate.assert_not_called()

    def test_raw_transcript_mode_is_no_longer_allowed(self):
        fake_note = NoteResult(markdown="# 标题\n\n## 简体中文文字稿\n\n已有字幕", transcript=None, audio_meta=None)

        with patch("app.routers.note.NoteGenerator") as generator_cls, patch(
            "app.routers.note.save_note_to_file"
        ), patch("app.routers.note.get_task_executor") as get_task_executor:
            get_task_executor.return_value.run.side_effect = lambda fn: fn()
            generator_cls.return_value.generate = Mock(return_value=fake_note)

            with self.assertRaises(HTTPException) as ctx:
                run_note_task(
                    task_id="subtitle-transcript-task",
                    video_url="https://www.bilibili.com/video/BV123",
                    platform="bilibili",
                    quality=DownloadQuality.fast,
                    mode="transcript",
                    model_name="demo-model",
                    provider_id="demo-provider",
                )

        self.assertEqual(ctx.exception.status_code, 400)
        generator_cls.return_value.generate.assert_not_called()

    def test_delete_task_removes_saved_task_from_refreshed_task_list(self):
        @asynccontextmanager
        async def lifespan(_app):
            yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(note_router.router, prefix='/api')

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / 'task-1.json').write_text(
                json.dumps(
                    {
                        'markdown': '# test',
                        'audio_meta': {
                            'video_id': 'BV1xx',
                            'platform': 'bilibili',
                            'title': '测试视频',
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding='utf-8',
            )

            original_router_output_dir = note_router.NOTE_OUTPUT_DIR
            try:
                note_router.NOTE_OUTPUT_DIR = str(output_dir)
                client = TestClient(app)

                delete_response = client.post(
                    '/api/delete_task',
                    json={'task_id': 'task-1', 'video_id': 'BV1xx', 'platform': 'bilibili'},
                )
                list_response = client.get('/api/task_list')
            finally:
                note_router.NOTE_OUTPUT_DIR = original_router_output_dir

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()['code'], 0)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()['data']['tasks'], [])

    def test_delete_task_by_task_id_keeps_other_records_for_same_video(self):
        @asynccontextmanager
        async def lifespan(_app):
            yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(note_router.router, prefix='/api')

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            for task_id in ('task-1', 'task-2'):
                (output_dir / f'{task_id}.json').write_text(
                    json.dumps(
                        {
                            'markdown': f'# {task_id}\n\n内容',
                            'mode': 'polished_transcript',
                            'audio_meta': {
                                'video_id': 'BV1same',
                                'platform': 'bilibili',
                                'title': f'测试视频 {task_id}',
                            },
                        },
                        ensure_ascii=False,
                    ),
                    encoding='utf-8',
                )

            original_router_output_dir = note_router.NOTE_OUTPUT_DIR
            try:
                note_router.NOTE_OUTPUT_DIR = str(output_dir)
                client = TestClient(app)

                delete_response = client.post(
                    '/api/delete_task',
                    json={'task_id': 'task-1', 'video_id': 'BV1same', 'platform': 'bilibili'},
                )
                list_response = client.get('/api/task_list')
            finally:
                note_router.NOTE_OUTPUT_DIR = original_router_output_dir

        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()['code'], 0)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([task['task_id'] for task in list_response.json()['data']['tasks']], ['task-2'])


    def test_update_task_markdown_persists_edited_transcript(self):
        @asynccontextmanager
        async def lifespan(_app):
            yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(note_router.router, prefix='/api')

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / 'task-edit.json').write_text(
                json.dumps(
                    {
                        'markdown': '# 测试视频\n\n旧内容',
                        'mode': 'polished_transcript',
                        'transcript': {'full_text': '旧内容', 'language': 'zh', 'raw': None, 'segments': []},
                        'audio_meta': {
                            'video_id': 'BVedit',
                            'platform': 'bilibili',
                            'title': '测试视频',
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding='utf-8',
            )

            original_router_output_dir = note_router.NOTE_OUTPUT_DIR
            try:
                note_router.NOTE_OUTPUT_DIR = str(output_dir)
                client = TestClient(app)

                update_response = client.post(
                    '/api/update_task_markdown',
                    json={
                        'task_id': 'task-edit',
                        'markdown': '# 测试视频\n\n用户修改后的内容',
                    },
                )
                status_response = client.get('/api/task_status/task-edit')
                saved_result = json.loads((output_dir / 'task-edit.json').read_text(encoding='utf-8'))
            finally:
                note_router.NOTE_OUTPUT_DIR = original_router_output_dir

        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()['code'], 0)
        self.assertEqual(saved_result['markdown'], '# 测试视频\n\n用户修改后的内容')
        self.assertEqual(saved_result['mode'], 'polished_transcript')
        self.assertEqual(
            status_response.json()['data']['result']['markdown'],
            '# 测试视频\n\n用户修改后的内容',
        )


if __name__ == "__main__":
    unittest.main()
