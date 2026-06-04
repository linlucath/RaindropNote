RETRYABLE_ERROR_TOKENS = (
    "error code: 524",
    "bad_response_status_code",
    "timed out",
    "timeout",
    "rate limit",
    "error code: 429",
    "error code: 500",
    "error code: 502",
    "error code: 503",
    "error code: 504",
    "apiconnectionerror",
    "connection error",
    "service unavailable",
)

RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504, 524}


def is_retryable_error(exc: Exception) -> bool:
    raw = str(exc).lower()
    if any(token in raw for token in RETRYABLE_ERROR_TOKENS):
        return True

    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    return status in RETRYABLE_STATUS_CODES


def retry_backoff_seconds(base_backoff_seconds: float, attempt_index: int) -> float:
    return base_backoff_seconds * (2 ** attempt_index)
