from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode

from pydantic import BaseModel


@dataclass(frozen=True)
class DouyinAwemeDetailRequest:
    url: str
    headers: dict
    params: dict
    signature_length: int


SENSITIVE_PARAM_KEYS = {"mstoken", "a_bogus", "signature"}


class BaseRequestModel(BaseModel):
    device_platform: str = "webapp"
    aid: str = "6383"
    channel: str = "channel_pc_web"
    pc_client_type: int = 1
    version_code: str = "290100"
    version_name: str = "29.1.0"
    cookie_enabled: str = "true"
    screen_width: int = 1920
    screen_height: int = 1080
    browser_language: str = "zh-CN"
    browser_platform: str = "Win32"
    browser_name: str = "Chrome"
    browser_version: str = "130.0.0.0"
    browser_online: str = "true"
    engine_name: str = "Blink"
    engine_version: str = "130.0.0.0"
    os_name: str = "Windows"
    os_version: str = "10"
    cpu_core_num: int = 12
    device_memory: int = 8
    platform: str = "PC"
    downlink: str = "10"
    effective_type: str = "4g"
    from_user_page: str = "1"
    locate_query: str = "false"
    need_time_list: str = "1"
    pc_libra_divert: str = "Windows"
    publish_video_strategy_type: str = "2"
    round_trip_time: str = "0"
    show_live_replay_strategy: str = "1"
    time_list_query: str = "0"
    whale_cut_token: str = ""
    update_version_code: str = "170400"
    msToken: str = None


def build_headers_config(headers_template: Mapping[str, Any], cookie: str | None) -> dict:
    headers = dict(headers_template)
    headers["Cookie"] = cookie
    return headers


def summarize_headers_for_log(headers: Mapping[str, Any]) -> dict:
    cookie = headers.get("Cookie")
    user_agent = headers.get("User-Agent") or ""
    return {
        "has_cookie": bool(cookie),
        "user_agent_length": len(user_agent),
        "accept_language": bool(headers.get("Accept-Language")),
        "referer": headers.get("Referer"),
    }


def redact_douyin_params(params: Mapping[str, Any]) -> dict:
    return {
        key: "<redacted>" if key.lower() in SENSITIVE_PARAM_KEYS and value else value
        for key, value in params.items()
    }


def build_aweme_detail_request(
    *,
    headers_template: Mapping[str, Any],
    cookie: str | None,
    aweme_id: str,
    ms_token: str,
    abogus_cls: Callable[[], Any],
    request_model_cls: Callable[[], Any],
    domain: str,
    quote_func: Callable[..., str] = quote,
    urlencode_func: Callable[[Mapping[str, Any]], str] = urlencode,
) -> DouyinAwemeDetailRequest:
    headers = build_headers_config(headers_template, cookie)
    params = request_model_cls().model_dump()
    params["msToken"] = ms_token
    params["aweme_id"] = aweme_id

    a_bogus = quote_func(abogus_cls().get_value(params), safe="")
    query_str = urlencode_func(params)
    url = f"{domain}/aweme/v1/web/aweme/detail/?{query_str}&a_bogus={a_bogus}"

    return DouyinAwemeDetailRequest(
        url=url,
        headers=headers,
        params=params,
        signature_length=len(a_bogus),
    )
