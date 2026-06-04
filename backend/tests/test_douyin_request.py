from app.downloaders.douyin_request import (
    build_aweme_detail_request,
    redact_douyin_params,
    summarize_headers_for_log,
)


class TinyRequestModel:
    def model_dump(self):
        return {
            "device_platform": "webapp",
            "msToken": None,
        }


class FakeABogus:
    last_params = None

    def get_value(self, params):
        FakeABogus.last_params = params.copy()
        return "signed/value=="


def test_build_aweme_detail_request_preserves_legacy_url_header_assembly():
    headers_template = {
        "Accept-Language": "zh-CN",
        "User-Agent": "test-agent",
        "Referer": "https://www.douyin.com/",
        "Cookie": None,
    }

    request = build_aweme_detail_request(
        headers_template=headers_template,
        cookie="sid_tt=test-cookie",
        aweme_id="1234567890",
        ms_token="ms-token-secret",
        abogus_cls=FakeABogus,
        request_model_cls=TinyRequestModel,
        domain="https://www.douyin.com",
    )

    assert request.headers == {
        "Accept-Language": "zh-CN",
        "User-Agent": "test-agent",
        "Referer": "https://www.douyin.com/",
        "Cookie": "sid_tt=test-cookie",
    }
    assert headers_template["Cookie"] is None
    assert FakeABogus.last_params == {
        "device_platform": "webapp",
        "msToken": "ms-token-secret",
        "aweme_id": "1234567890",
    }
    assert request.url == (
        "https://www.douyin.com/aweme/v1/web/aweme/detail/"
        "?device_platform=webapp&msToken=ms-token-secret&aweme_id=1234567890"
        "&a_bogus=signed%2Fvalue%3D%3D"
    )
    assert request.signature_length == len("signed%2Fvalue%3D%3D")


def test_douyin_request_log_helpers_redact_sensitive_values():
    headers_summary = summarize_headers_for_log(
        {
            "Cookie": "sid_tt=test-cookie",
            "User-Agent": "test-agent",
            "Accept-Language": "zh-CN",
            "Referer": "https://www.douyin.com/",
        }
    )
    params_summary = redact_douyin_params(
        {
            "msToken": "ms-token-secret",
            "a_bogus": "a-bogus-secret",
            "signature": "signature-secret",
            "aweme_id": "1234567890",
        }
    )

    combined = f"{headers_summary} {params_summary}"

    assert headers_summary == {
        "has_cookie": True,
        "user_agent_length": len("test-agent"),
        "accept_language": True,
        "referer": "https://www.douyin.com/",
    }
    assert params_summary == {
        "msToken": "<redacted>",
        "a_bogus": "<redacted>",
        "signature": "<redacted>",
        "aweme_id": "1234567890",
    }
    assert "sid_tt=test-cookie" not in combined
    assert "ms-token-secret" not in combined
    assert "a-bogus-secret" not in combined
    assert "signature-secret" not in combined
