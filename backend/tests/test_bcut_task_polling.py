import pytest

from app.transcriber.bcut_task_polling import wait_for_completed_task_result


def test_wait_for_completed_task_result_returns_completed_response():
    responses = iter([
        {"state": 1},
        {"state": 2},
        {"state": 4, "result": "done"},
    ])

    result = wait_for_completed_task_result(
        lambda: next(responses),
        max_retries=5,
        sleep_seconds=0,
        sleep=lambda _seconds: None,
    )

    assert result == {"state": 4, "result": "done"}


def test_wait_for_completed_task_result_raises_on_failed_state():
    with pytest.raises(Exception, match="B站ASR任务失败，状态码: 3"):
        wait_for_completed_task_result(
            lambda: {"state": 3},
            max_retries=5,
            sleep_seconds=0,
            sleep=lambda _seconds: None,
        )


def test_wait_for_completed_task_result_raises_when_retries_exhausted():
    with pytest.raises(Exception, match="B站ASR任务未能完成，状态: 2"):
        wait_for_completed_task_result(
            lambda: {"state": 2},
            max_retries=2,
            sleep_seconds=0,
            sleep=lambda _seconds: None,
        )
