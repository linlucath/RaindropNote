import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app.enmus.note_enums import DownloadQuality
from app.routers import batch


class TestBatchTranscriptConcurrency(unittest.TestCase):
    def test_run_batch_processes_transcript_items_in_parallel_when_concurrency_is_two(self):
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
            mode='polished_transcript',
            quality=DownloadQuality.fast,
            skip_existing=False,
            concurrency=2,
        )
        batch_id = 'batch-concurrency'
        state = {'active': 0, 'peak_active': 0}
        state_lock = threading.Lock()

        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict('app.routers.batch._batches', {
                    batch_id: batch.create_batch_payload(batch_id=batch_id, request=request),
                }, clear=True), \
                patch('app.routers.batch.BATCH_OUTPUT_DIR', Path(tmp) / 'batches'), \
                patch('app.routers.batch.NOTE_OUTPUT_DIR', Path(tmp)), \
                patch('app.routers.batch.uuid.uuid4', side_effect=['task-1', 'task-2']), \
                patch('app.routers.batch.run_note_task') as run_note_task:

            def run_note_task_side_effect(**kwargs):
                task_id = kwargs['task_id']
                with state_lock:
                    state['active'] += 1
                    state['peak_active'] = max(state['peak_active'], state['active'])
                time.sleep(0.05)
                (Path(tmp) / f'{task_id}.json').write_text(
                    json.dumps({'ok': True}),
                    encoding='utf-8',
                )
                with state_lock:
                    state['active'] -= 1

            run_note_task.side_effect = run_note_task_side_effect

            batch.run_batch(batch_id, request)

        self.assertEqual(state['peak_active'], 2)
