class _StatusError(Exception):
    def __init__(self, message: str, *, status_code=None, status=None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code
        if status is not None:
            self.status = status


def test_is_retryable_error_matches_legacy_text_tokens():
    from app.gpt.retry_policy import is_retryable_error

    retryable_messages = [
        "Error code: 524 - bad_response_status_code",
        "request timed out while reading response",
        "provider hit a rate limit",
        "APIConnectionError: connection error",
        "service unavailable",
    ]

    for message in retryable_messages:
        assert is_retryable_error(Exception(message)), message

    assert not is_retryable_error(Exception("insufficient_user_quota"))
    assert not is_retryable_error(Exception("invalid api key"))


def test_is_retryable_error_matches_legacy_status_attributes():
    from app.gpt.retry_policy import is_retryable_error

    assert is_retryable_error(_StatusError("retry by status_code", status_code=429))
    assert is_retryable_error(_StatusError("retry by status", status=524))
    assert is_retryable_error(_StatusError("conflict retries", status_code=409))

    assert not is_retryable_error(_StatusError("client error", status_code=400))
    assert not is_retryable_error(_StatusError("teapot", status=418))


def test_retry_backoff_seconds_is_exponential_from_zero_based_attempt():
    from app.gpt.retry_policy import retry_backoff_seconds

    assert retry_backoff_seconds(base_backoff_seconds=1.5, attempt_index=0) == 1.5
    assert retry_backoff_seconds(base_backoff_seconds=1.5, attempt_index=1) == 3.0
    assert retry_backoff_seconds(base_backoff_seconds=1.5, attempt_index=2) == 6.0
