import functools
import logging
import time

logger = logging.getLogger(__name__)

def timeit(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        duration = end - start
        logger.debug("%s executed in %.4f seconds", func.__name__, duration)
        return result
    return wrapper
