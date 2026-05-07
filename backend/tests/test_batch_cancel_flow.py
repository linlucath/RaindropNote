import json
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.enmus.note_enums import DownloadQuality
from app.enmus.task_status_enums import TaskStatus
from app.routers import batch
from app.services.progress_state import read_task_status, write_task_status


class TestBatchCancelFlow(unittest.TestCase):
    def _make_app(self):
        @asynccontextmanager
        async def lifespan(_app):
            yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(batch.router, prefix='/api')
        return app

    def test_cancel_batch_marks_batch_as_cancelling_and_propagates_to_current_child_task(self):
        app = self._make_app()
        batch_id = 'batch-1'

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict('app.routers.batch._batches', {
                    batch_id: {
                        'batch_id': batch_id,
                        'title': '批量文字稿任务',
                        'source_label': 'Bilibili',
                        'status': 'RUNNING',
                        'created_at': '2026-05-07T00:00:00+00:00',
                        'updated_at': '2026-05-07T00:00:00+00:00',
                        'cancel_requested': False,
                        'current_item_title': '示例视频',
                        'current_item_index': 0,
                        'total': 2,
                        'completed': 0,
                        'items': [
                            {
                                'video_id': 'BV123',
                                'video_url': 'https://www.bilibili.com/video/BV123',
                                'title': '示例视频',
                                'status': 'RUNNING',
                                'task_id': 'task-1',
                                'message': '',
                            },
                            {
                                'video_id': 'BV456',
                                'video_url': 'https://www.bilibili.com/video/BV456',
                                'title': '待开始视频',
                                'status': 'PENDING',
                                'task_id': None,
                                'message': '',
                            },
                        ],
                    }
                }, clear=True), \
                patch('app.routers.batch.BATCH_OUTPUT_DIR', Path(tmp) / 'batches'), \
                patch('app.routers.batch.NOTE_OUTPUT_DIR', Path(tmp) / 'notes'):
            write_task_status(
                task_id='task-1',
                output_dir=Path(tmp) / 'notes',
                status=TaskStatus.PARSING,
                title='示例视频',
                platform='bilibili',
            )

            client = TestClient(app)
            response = client.post('/api/batch/cancel', json={'batch_id': batch_id})

            self.assertEqual(response.status_code, 200)
            payload = response.json()['data']
            self.assertEqual(payload['status'], 'CANCELLING')
            self.assertTrue(payload['cancel_requested'])

            task_status = read_task_status(task_id='task-1', output_dir=Path(tmp) / 'notes')
            self.assertEqual(task_status['status'], TaskStatus.CANCELLING.value)

            batch_file = Path(tmp) / 'batches' / f'{batch_id}.json'
            self.assertTrue(batch_file.exists())
            saved_batch = json.loads(batch_file.read_text(encoding='utf-8'))
            self.assertEqual(saved_batch['status'], 'CANCELLING')
            self.assertTrue(saved_batch['cancel_requested'])

    def test_run_batch_stops_starting_new_items_after_cancel_requested(self):
        batch_id = 'batch-2'
        request = batch.BatchStartRequest(
            videos=[
                batch.BatchVideo(
                    video_id='BV123',
                    video_url='https://www.bilibili.com/video/BV123',
                    title='第一个视频',
                ),
                batch.BatchVideo(
                    video_id='BV456',
                    video_url='https://www.bilibili.com/video/BV456',
                    title='第二个视频',
                ),
            ],
            mode='transcript',
            quality=DownloadQuality.fast,
            skip_existing=False,
        )

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict('app.routers.batch._batches', {
                    batch_id: batch.create_batch_payload(batch_id=batch_id, request=request),
                }, clear=True), \
                patch('app.routers.batch.BATCH_OUTPUT_DIR', Path(tmp) / 'batches'), \
                patch('app.routers.batch.NOTE_OUTPUT_DIR', Path(tmp) / 'notes'), \
                patch('app.routers.batch.uuid.uuid4', side_effect=['task-1', 'task-2']), \
                patch('app.routers.batch.run_note_task') as run_note_task:

            def complete_first_task_and_request_cancel(**kwargs):
                task_id = kwargs['task_id']
                (Path(tmp) / 'notes').mkdir(parents=True, exist_ok=True)
                (Path(tmp) / 'notes' / f'{task_id}.json').write_text(
                    json.dumps({'ok': True}),
                    encoding='utf-8',
                )
                batch._update_batch(batch_id, status='CANCELLING', cancel_requested=True)

            run_note_task.side_effect = complete_first_task_and_request_cancel

            batch.run_batch(batch_id, request)

            self.assertEqual(run_note_task.call_count, 1)
            saved_batch = batch._batches[batch_id]
            self.assertEqual(saved_batch['status'], 'CANCELLED')
            self.assertTrue(saved_batch['cancel_requested'])
            self.assertIsNone(saved_batch['current_item_title'])
            self.assertIsNone(saved_batch['current_item_index'])
            self.assertEqual(saved_batch['items'][0]['status'], 'SUCCESS')
            self.assertEqual(saved_batch['items'][1]['status'], 'CANCELLED')

    def test_cancel_batch_is_idempotent_for_cancelled_batch(self):
        app = self._make_app()
        batch_id = 'batch-3'

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict('app.routers.batch._batches', {
                    batch_id: {
                        'batch_id': batch_id,
                        'title': '批量文字稿任务',
                        'source_label': 'Bilibili',
                        'status': 'CANCELLED',
                        'created_at': '2026-05-07T00:00:00+00:00',
                        'updated_at': '2026-05-07T00:00:00+00:00',
                        'cancel_requested': True,
                        'current_item_title': None,
                        'current_item_index': None,
                        'total': 1,
                        'completed': 1,
                        'items': [
                            {
                                'video_id': 'BV123',
                                'video_url': 'https://www.bilibili.com/video/BV123',
                                'title': '示例视频',
                                'status': 'CANCELLED',
                                'task_id': 'task-3',
                                'message': '批量任务已取消',
                            }
                        ],
                    }
                }, clear=True), \
                patch('app.routers.batch.BATCH_OUTPUT_DIR', Path(tmp) / 'batches'), \
                patch('app.routers.batch.NOTE_OUTPUT_DIR', Path(tmp) / 'notes'):
            client = TestClient(app)
            response = client.post('/api/batch/cancel', json={'batch_id': batch_id})

            self.assertEqual(response.status_code, 200)
            payload = response.json()['data']
            self.assertEqual(payload['status'], 'CANCELLED')
            self.assertTrue(payload['cancel_requested'])

