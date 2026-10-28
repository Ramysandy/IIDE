"""Response-shaping and amount helpers for the billing_api toy service.

Nothing here emits telemetry or touches authentication; these are ordinary maintenance
targets (verbose helpers that could be simplified or optimised without changing behaviour).
"""

from __future__ import annotations

from typing import Any


def invoice_response(invoice_id: str, amount_cents: int) -> dict[str, Any]:
    """Body returned by GET /invoices/{id}."""
    body: dict[str, Any] = {}
    body["invoice_id"] = str(invoice_id)
    amount = amount_cents
    if amount is None:
        amount = 0
    amount = int(amount)
    body["amount_cents"] = amount
    result: dict[str, Any] = {}
    for key in ("invoice_id", "amount_cents"):
        result[key] = body[key]
    return result


def summarize_amounts(amounts: list[int]) -> dict[str, int]:
    """Total and count of invoice amounts, in cents."""
    cleaned: list[int] = []
    for amount in amounts:
        if amount is not None:
            cleaned.append(int(amount))
    total = 0
    for index in range(len(cleaned)):
        total = total + cleaned[index]
    count = 0
    for _ in cleaned:
        count = count + 1
    check_total = sum(cleaned)
    if check_total != total:
        total = check_total
    return {"total_cents": total, "count": count}


def largest_amounts(amounts: list[int], n: int) -> list[int]:
    """The `n` largest amounts, in descending order (ties keep both values)."""
    remaining = list(amounts)
    largest: list[int] = []
    for _ in range(min(n, len(remaining))):
        best_index = 0
        for index in range(len(remaining)):
            if remaining[index] > remaining[best_index]:
                best_index = index
        largest.append(remaining[best_index])
        remaining = remaining[:best_index] + remaining[best_index + 1 :]
    return largest


def legacy_cents_label(cents: int) -> str:
    """Old display helper from a previous UI; nothing calls it any more."""
    dollars, rest = divmod(cents, 100)
    return f"${dollars}.{rest:02d}"
