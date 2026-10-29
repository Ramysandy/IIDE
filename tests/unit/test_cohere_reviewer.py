"""Cohere LLM reviewer. Network is mocked; the real key is never required."""

from __future__ import annotations

import json

import httpx

from iide.analysis.cohere_reviewer import parse_verdict, review_diff
from iide.analysis.comparison import llm_reviewer
from iide.config import REPO_ROOT

CFG = {
    "prompt": "Reply with VERDICT: EROSION|NONE|UNKNOWN",
    "provider": "cohere",
    "model_id": "command-r7b-12-2024",
    "env_key": "COHERE_API_KEY",
    "endpoint": "https://api.cohere.com/v2/chat",
    "max_tokens": 256,
    "temperature": 0,
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_default_llm_reviewer_does_not_call_the_network(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cohere_testplaceholderkeyvalue0000000000")
    result = llm_reviewer("diff --git a/app/x.py b/app/x.py")
    assert result.prediction == "UNAVAILABLE"
    assert "not claimed as run" in result.detail


def test_live_path_is_unavailable_without_a_key(monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    result = llm_reviewer("diff", call_llm=True)
    assert result.prediction == "UNAVAILABLE"
    assert "COHERE_API_KEY" in result.detail


def test_parses_erosion_and_none_and_unknown():
    assert parse_verdict("VERDICT: EROSION\n_emit_lockout")[0] == "EROSION"
    assert parse_verdict("noise\nverdict: none\n")[0] == "NONE"
    assert parse_verdict("VERDICT: UNKNOWN")[0] == "UNAVAILABLE"
    assert parse_verdict("looks like erosion to me")[0] == "UNAVAILABLE"


def test_mocked_cohere_success_is_erosion_and_redacts_the_key(monkeypatch):
    leaked = "cohere_testplaceholderkeyvalue0000000000"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {leaked}"
        body = json.loads(request.content.decode())
        assert body["model"] == "command-r7b-12-2024"
        assert "oracle" not in body["messages"][0]["content"].lower()
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": f"VERDICT: EROSION\nkey was {leaked} _emit_lockout",
                        }
                    ],
                },
                "usage": {"tokens": {"input_tokens": 11, "output_tokens": 7}},
            },
        )

    monkeypatch.setenv("COHERE_API_KEY", leaked)
    result = review_diff("diff --git a/app/service.py", CFG, client=_client(handler))
    assert result.prediction == "EROSION"
    assert result.available is True
    assert leaked not in result.detail
    assert "[REDACTED]" in result.detail
    assert result.numeric["http_status"] == 200
    assert result.numeric["input_tokens"] == 11


def test_http_error_and_bad_json_are_unavailable_not_erosion(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cohere_testplaceholderkeyvalue0000000000")

    def unauthorized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid api key")

    denied = review_diff("diff", CFG, client=_client(unauthorized))
    assert denied.prediction == "UNAVAILABLE"
    assert denied.available is False
    assert "401" in denied.detail

    def not_json(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    broken = review_diff("diff", CFG, client=_client(not_json))
    assert broken.prediction == "UNAVAILABLE"


def test_frozen_prompt_contains_no_oracle_labels():
    text = (REPO_ROOT / "configs" / "llm_reviewer.yaml").read_text(encoding="utf-8")
    assert "command-r7b-12-2024" in text
    lowered = text.lower()
    assert "filter_lockout" not in lowered
    assert "oracle_y" not in lowered
    assert "confirmed erosion" not in lowered


def test_transport_failure_is_unavailable(monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "cohere_testplaceholderkeyvalue0000000000")

    class RaisingClient:
        def post(self, *args, **kwargs):
            raise httpx.ConnectError("dns")

    result = review_diff("diff", CFG, client=RaisingClient())  # type: ignore[arg-type]
    assert result.prediction == "UNAVAILABLE"
    assert "failed" in result.detail.lower()
