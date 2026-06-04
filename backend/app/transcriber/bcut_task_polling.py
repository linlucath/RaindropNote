import time
from typing import Callable, Optional


COMPLETED_STATE = 4
FAILED_STATE = 3


def wait_for_completed_task_result(
    query_result: Callable[[], dict],
    *,
    max_retries: int = 500,
    sleep_seconds: float = 1,
    sleep: Callable[[float], None] = time.sleep,
    logger=None,
) -> dict:
    task_resp: Optional[dict] = None

    for i in range(max_retries):
        task_resp = query_result()

        if task_resp["state"] == COMPLETED_STATE:
            return task_resp
        if task_resp["state"] == FAILED_STATE:
            error_msg = f"B站ASR任务失败，状态码: {task_resp['state']}"
            if logger:
                logger.error(error_msg)
            raise Exception(error_msg)

        if i % 10 == 0 and logger:
            logger.info(f"转录进行中... {i}/{max_retries}")

        sleep(sleep_seconds)

    error_msg = f"B站ASR任务未能完成，状态: {task_resp.get('state') if task_resp else 'Unknown'}"
    if logger:
        logger.error(error_msg)
    raise Exception(error_msg)
