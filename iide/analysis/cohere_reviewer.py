"""Cohere Chat adapter for the frozen LLM-diff reviewer (spec 15 #4).

Default comparison path never calls the network. A live call needs ``--with-llm`` and
``COHERE_API_KEY`` in the environment (never committed). Trial keys are limited; the
calibration suite is four diffs and this module does not retry on failure.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any

import httpx

from iide.analysis.comparison import MethodResult, Prediction
from iide.runner.agent_interface import redact

VERDICT_RE = re.compile(r"VERDICT:\s*(EROSION|NONE|UNKNOWN)\b", re.IGNORECASE)
DEFAULT_ENDPOINT = "https://api.cohere.com/v2/chat"
DEFAULT_MODEL = "command-r7b-12-2024"
DEFAULT_ENV_KEY = "COHERE_API_KEY"
DEFAULT_MAX_TOKENS = 256
DEFAULT_TIMEOUT = 45.0


def review_diff(
    diff_text: str,
    cfg: Mapping[str, Any],
    *,
    client: httpx.Client | None = None,
) -> MethodResult:
    """Call Cohere with the frozen prompt. Never invent EROSION on a failed call."""
    prompt = str(cfg.get("prompt") or "")
    env_key = str(cfg.get("env_key") or DEFAULT_ENV_KEY)
    model_id = str(cfg.get("model_id") or DEFAULT_MODEL)
    endpoint = str(cfg.get("endpoint") or DEFAULT_ENDPOINT)
    max_tokens = int(cfg.get("max_tokens") or DEFAULT_MAX_TOKENS)
    temperature = float(cfg.get("temperature") if cfg.get("temperature") is not None else 0)
    key = os.environ.get(env_key, "").strip()
    numeric: dict[str, float | int | None] = {
        "prompt_chars": len(prompt),
        "diff_chars": len(diff_text),
    }
    if not key:
        return MethodResult(
            method_id="llm_reviewer",
            prediction="UNAVAILABLE",
            available=False,
            tool_version=model_id,
            detail=(
                f"{env_key} is not set; Cohere was not called and is not claimed as run. "
                "Prompt is frozen and contains no oracle labels."
            ),
            numeric=numeric,
        )
    body = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": f"{prompt.rstrip()}\n\n--- unified diff ---\n{diff_text}",
            }
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Client-Name": "iide-llm-reviewer",
    }
    try:
        response = _post(endpoint, headers, body, client)
    except httpx.HTTPError as exc:
        return MethodResult(
            method_id="llm_reviewer",
            prediction="UNAVAILABLE",
            available=False,
            tool_version=model_id,
            detail=redact(f"Cohere request failed: {exc}", [key]),
            numeric=numeric,
        )
    numeric["http_status"] = response.status_code
    raw = redact(response.text or "", [key])
    if response.status_code != 200:
        return MethodResult(
            method_id="llm_reviewer",
            prediction="UNAVAILABLE",
            available=False,
            tool_version=model_id,
            detail=redact(
                f"Cohere HTTP {response.status_code}; not claimed as a review. {raw[:400]}",
                [key],
            ),
            numeric=numeric,
        )
    try:
        payload = response.json()
    except ValueError:
        return MethodResult(
            method_id="llm_reviewer",
            prediction="UNAVAILABLE",
            available=False,
            tool_version=model_id,
            detail="Cohere returned non-JSON; not claimed as a review.",
            numeric=numeric,
        )
    text = redact(_assistant_text(payload), [key])
    _fill_usage(numeric, payload)
    prediction, reason = parse_verdict(text)
    return MethodResult(
        method_id="llm_reviewer",
        prediction=prediction,
        available=prediction != "UNAVAILABLE",
        tool_version=model_id,
        detail=redact(f"{reason}: {text[:600]}", [key]),
        numeric=numeric,
    )


def parse_verdict(text: str) -> tuple[Prediction, str]:
    """Map the frozen ``VERDICT:`` line. Unparseable / UNKNOWN is UNAVAILABLE, not EROSION."""
    match = VERDICT_RE.search(text or "")
    if match is None:
        return "UNAVAILABLE", "no VERDICT line"
    token = match.group(1).upper()
    if token == "UNKNOWN":
        return "UNAVAILABLE", "model returned UNKNOWN"
    if token in {"EROSION", "NONE"}:
        return token, f"VERDICT {token}"  # type: ignore[return-value]
    return "UNAVAILABLE", "unrecognised VERDICT"


def _post(
    endpoint: str,
    headers: dict[str, str],
    body: dict[str, Any],
    client: httpx.Client | None,
) -> httpx.Response:
    if client is not None:
        return client.post(endpoint, headers=headers, json=body)
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as owned:
        return owned.post(endpoint, headers=headers, json=body)


def _assistant_text(payload: Mapping[str, Any]) -> str:
    message = payload.get("message")
    if not isinstance(message, Mapping):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, Mapping) and item.get("type") in {None, "text"}:
            parts.append(str(item.get("text") or ""))
    return "\n".join(p for p in parts if p)


def _fill_usage(numeric: dict[str, float | int | None], payload: Mapping[str, Any]) -> None:
    usage = payload.get("usage")
    if not isinstance(usage, Mapping):
        return
    tokens = usage.get("tokens")
    billed = usage.get("billed_units")
    source = tokens if isinstance(tokens, Mapping) else billed
    if not isinstance(source, Mapping):
        return
    inp, out = source.get("input_tokens"), source.get("output_tokens")
    if isinstance(inp, (int, float)):
        numeric["input_tokens"] = int(inp)
    if isinstance(out, (int, float)):
        numeric["output_tokens"] = int(out)
