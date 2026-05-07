import json
import tempfile
import unittest
from time import sleep
from pathlib import Path

from app.enmus.task_status_enums import TaskStatus
from app.services.progress_state import (
    is_terminal_task_status,
    read_task_status,
    request_task_cancel,
    write_task_status,
)


class TestProgressState(unittest.TestCase):
    def test_write_task_status_persists_metadata_and_updated_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            write_task_status(
                task_id='task-1',
                output_dir=output_dir,
                status=TaskStatus.PENDING,
                message='queued',
                title='Demo title',
                platform='bilibili',
            )

            payload = json.loads((output_dir / 'task-1.status.json').read_text(encoding='utf-8'))

        self.assertEqual(
            set(payload.keys()),
            {'status', 'message', 'updated_at', 'created_at', 'title', 'platform'},
        )
        self.assertEqual(payload['status'], TaskStatus.PENDING.value)
        self.assertEqual(payload['message'], 'queued')
        self.assertEqual(payload['title'], 'Demo title')
        self.assertEqual(payload['platform'], 'bilibili')
        self.assertIsNotNone(payload['created_at'])
        self.assertIsNotNone(payload['updated_at'])
        self.assertEqual(payload['created_at'], payload['updated_at'])

    def test_write_task_status_preserves_created_at_and_reuses_existing_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            write_task_status(
                task_id='task-1',
                output_dir=output_dir,
                status=TaskStatus.PENDING,
                message='queued',
                title='Demo title',
                platform='bilibili',
            )
            initial_payload = read_task_status(task_id='task-1', output_dir=output_dir)

            sleep(0.001)

            write_task_status(
                task_id='task-1',
                output_dir=output_dir,
                status=TaskStatus.DOWNLOADING,
            )
            updated_payload = read_task_status(task_id='task-1', output_dir=output_dir)

        self.assertEqual(updated_payload['status'], TaskStatus.DOWNLOADING.value)
        self.assertEqual(updated_payload['created_at'], initial_payload['created_at'])
        self.assertGreater(updated_payload['updated_at'], initial_payload['updated_at'])
        self.assertEqual(updated_payload['message'], 'queued')
        self.assertEqual(updated_payload['title'], 'Demo title')
        self.assertEqual(updated_payload['platform'], 'bilibili')

    def test_request_task_cancel_marks_cancelling_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            write_task_status(
                task_id='task-1',
                output_dir=output_dir,
                status=TaskStatus.DOWNLOADING,
                title='Downloading demo',
                platform='youtube',
            )
            initial_payload = read_task_status(task_id='task-1', output_dir=output_dir)

            request_task_cancel(task_id='task-1', output_dir=output_dir)
            cancelled_payload = read_task_status(task_id='task-1', output_dir=output_dir)

            request_task_cancel(task_id='task-1', output_dir=output_dir)
            repeated_payload = read_task_status(task_id='task-1', output_dir=output_dir)

        self.assertEqual(cancelled_payload['status'], 'CANCELLING')
        self.assertEqual(repeated_payload['status'], 'CANCELLING')
        self.assertEqual(cancelled_payload['title'], 'Downloading demo')
        self.assertEqual(cancelled_payload['platform'], 'youtube')
        self.assertEqual(cancelled_payload['created_at'], initial_payload['created_at'])
        self.assertEqual(repeated_payload['created_at'], initial_payload['created_at'])
        self.assertGreaterEqual(cancelled_payload['updated_at'], initial_payload['updated_at'])
        self.assertGreaterEqual(repeated_payload['updated_at'], cancelled_payload['updated_at'])

    def test_request_task_cancel_keeps_terminal_status_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            write_task_status(
                task_id='task-1',
                output_dir=output_dir,
                status=TaskStatus.SUCCESS,
                message='done',
                title='Completed demo',
                platform='youtube',
            )
            terminal_payload = read_task_status(task_id='task-1', output_dir=output_dir)

            request_task_cancel(task_id='task-1', output_dir=output_dir)
            payload_after_cancel = read_task_status(task_id='task-1', output_dir=output_dir)

        self.assertEqual(payload_after_cancel['status'], TaskStatus.SUCCESS.value)
        self.assertEqual(payload_after_cancel['message'], 'done')
        self.assertEqual(payload_after_cancel['title'], 'Completed demo')
        self.assertEqual(payload_after_cancel['platform'], 'youtube')
        self.assertEqual(payload_after_cancel['created_at'], terminal_payload['created_at'])
        self.assertEqual(payload_after_cancel['updated_at'], terminal_payload['updated_at'])

    def test_request_task_cancel_keeps_failed_status_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            write_task_status(
                task_id='task-1',
                output_dir=output_dir,
                status=TaskStatus.FAILED,
                message='boom',
                title='Failed demo',
                platform='youtube',
            )
            terminal_payload = read_task_status(task_id='task-1', output_dir=output_dir)

            request_task_cancel(task_id='task-1', output_dir=output_dir)
            payload_after_cancel = read_task_status(task_id='task-1', output_dir=output_dir)

        self.assertEqual(payload_after_cancel['status'], TaskStatus.FAILED.value)
        self.assertEqual(payload_after_cancel['message'], 'boom')
        self.assertEqual(payload_after_cancel['title'], 'Failed demo')
        self.assertEqual(payload_after_cancel['platform'], 'youtube')
        self.assertEqual(payload_after_cancel['created_at'], terminal_payload['created_at'])
        self.assertEqual(payload_after_cancel['updated_at'], terminal_payload['updated_at'])

    def test_request_task_cancel_keeps_cancelled_string_status_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            write_task_status(
                task_id='task-1',
                output_dir=output_dir,
                status='CANCELLED',
                message='stopped',
                title='Cancelled demo',
                platform='youtube',
            )
            terminal_payload = read_task_status(task_id='task-1', output_dir=output_dir)

            request_task_cancel(task_id='task-1', output_dir=output_dir)
            payload_after_cancel = read_task_status(task_id='task-1', output_dir=output_dir)

        self.assertEqual(payload_after_cancel['status'], 'CANCELLED')
        self.assertEqual(payload_after_cancel['message'], 'stopped')
        self.assertEqual(payload_after_cancel['title'], 'Cancelled demo')
        self.assertEqual(payload_after_cancel['platform'], 'youtube')
        self.assertEqual(payload_after_cancel['created_at'], terminal_payload['created_at'])
        self.assertEqual(payload_after_cancel['updated_at'], terminal_payload['updated_at'])

    def test_request_task_cancel_is_noop_for_missing_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            payload_after_cancel = request_task_cancel(task_id='missing-task', output_dir=output_dir)

        self.assertEqual(payload_after_cancel, {})
        self.assertFalse((output_dir / 'missing-task.status.json').exists())

    def test_progress_state_reads_missing_files_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            payload = read_task_status(task_id='missing-task', output_dir=output_dir)

        self.assertEqual(payload, {})

    def test_progress_state_reads_invalid_json_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / 'broken.status.json').write_text('{not-json', encoding='utf-8')

            payload = read_task_status(task_id='broken', output_dir=output_dir)

        self.assertEqual(payload, {})

    def test_progress_state_reads_non_dict_payload_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / 'list.status.json').write_text(
                json.dumps(['unexpected', 'payload']),
                encoding='utf-8',
            )

            payload = read_task_status(task_id='list', output_dir=output_dir)

        self.assertEqual(payload, {})

    def test_is_terminal_task_status_only_returns_true_for_terminal_states(self):
        self.assertFalse(is_terminal_task_status(TaskStatus.PENDING))
        self.assertFalse(is_terminal_task_status('DOWNLOADING'))
        self.assertTrue(is_terminal_task_status(TaskStatus.SUCCESS))
        self.assertTrue(is_terminal_task_status(TaskStatus.FAILED))
        self.assertTrue(is_terminal_task_status('CANCELLED'))


if __name__ == '__main__':
    unittest.main()
