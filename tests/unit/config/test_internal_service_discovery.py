from __future__ import annotations

from config.internal_service_discovery import http_base_from_health_or_ready_url


def test_http_base_from_ready_url_strips_path_query_fragment() -> None:
    assert (
        http_base_from_health_or_ready_url("http://llm-orchestrator:8070/ready")
        == "http://llm-orchestrator:8070"
    )
    assert (
        http_base_from_health_or_ready_url("http://live-broker:8120/ready?x=1#frag")
        == "http://live-broker:8120"
    )


def test_http_base_empty_or_invalid() -> None:
    assert http_base_from_health_or_ready_url("") == ""
    assert http_base_from_health_or_ready_url("   ") == ""
    assert http_base_from_health_or_ready_url("/ready") == ""
    assert http_base_from_health_or_ready_url("not-a-url") == ""


def test_http_base_https_with_port() -> None:
    assert (
        http_base_from_health_or_ready_url("https://worker.internal:9443/healthz")
        == "https://worker.internal:9443"
    )
