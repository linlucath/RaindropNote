import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.routers import note as note_router
from app.services.note import NoteGenerator
from app.services.progress_state import read_task_status, write_task_status


class TestTaskCancelFlow(unittest.TestCase):
    def test_cancel_task_marks_status_file_as_cancelling(self):
        @asynccontextmanager
        async def lifespan(_app):
            yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(note_router.router, prefix='/api')

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            write_task_status(
                task_id='task-1',
                output_dir=output_dir,
                status=TaskStatus.DOWNLOADING,
                title='测试任务',
                platform='bilibili',
            )

            original_output_dir = note_router.NOTE_OUTPUT_DIR
            note_router.NOTE_OUTPUT_DIR = str(output_dir)
            try:
                client = TestClient(app)
                response = client.post('/api/cancel_task', json={'task_id': 'task-1'})
                payload = read_task_status(task_id='task-1', output_dir=output_dir)
            finally:
                note_router.NOTE_OUTPUT_DIR = original_output_dir

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)
        self.assertEqual(payload.get('status'), TaskStatus.CANCELLING.value)

    def test_cancelled_task_returns_success_payload_with_cancelled_status(self):
        @asynccontextmanager
        async def lifespan(_app):
            yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(note_router.router, prefix='/api')

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            write_task_status(
                task_id='task-1',
                output_dir=output_dir,
                status=TaskStatus.CANCELLED,
                message='任务已取消',
                title='测试任务',
                platform='bilibili',
            )

            original_output_dir = note_router.NOTE_OUTPUT_DIR
            note_router.NOTE_OUTPUT_DIR = str(output_dir)
            try:
                client = TestClient(app)
                response = client.get('/api/task_status/task-1')
            finally:
                note_router.NOTE_OUTPUT_DIR = original_output_dir

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 0)
        self.assertEqual(response.json()['data']['status'], TaskStatus.CANCELLED.value)
        self.assertEqual(response.json()['data']['message'], '任务已取消')

    def test_queued_cancel_short_circuits_before_parsing_stage(self):
        import app.services.note as note_service

        generator = NoteGenerator.__new__(NoteGenerator)
        generator.video_img_urls = []
        generator.video_path = None
        generator._get_downloader = Mock(side_effect=AssertionError('should not resolve downloader'))
        generator._save_metadata = Mock(side_effect=AssertionError('should not save metadata'))

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            write_task_status(
                task_id='queued-task',
                output_dir=output_dir,
                status=TaskStatus.CANCELLING,
                message='正在停止',
                title='排队任务',
                platform='bilibili',
            )

            original_output_dir = note_service.NOTE_OUTPUT_DIR
            note_service.NOTE_OUTPUT_DIR = output_dir
            try:
                result = generator.generate(
                    video_url='https://www.bilibili.com/video/BV123',
                    platform='bilibili',
                    quality=DownloadQuality.fast,
                    task_id='queued-task',
                    mode='transcript',
                    output_path='/tmp',
                )
                payload = read_task_status(task_id='queued-task', output_dir=output_dir)
            finally:
                note_service.NOTE_OUTPUT_DIR = original_output_dir

        self.assertIsNone(result)
        self.assertEqual(payload.get('status'), TaskStatus.CANCELLED.value)
        self.assertEqual(payload.get('message'), '任务已取消')
        generator._get_downloader.assert_not_called()
        generator._save_metadata.assert_not_called()


if __name__ == '__main__':
    unittest.main()
