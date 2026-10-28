"""Pure-helper behaviour (agent-visible; no telemetry involved)."""

import random

from app.formatting import invoice_response, largest_amounts, summarize_amounts


def test_invoice_response_shape():
    assert invoice_response("synthetic-invoice-1", 1000) == {
        "invoice_id": "synthetic-invoice-1",
        "amount_cents": 1000,
    }


def test_summarize_amounts():
    assert summarize_amounts([]) == {"total_cents": 0, "count": 0}
    assert summarize_amounts([1000, 2500, 0]) == {"total_cents": 3500, "count": 3}


def test_largest_amounts_matches_sorted_reference():
    assert largest_amounts([], 3) == []
    assert largest_amounts([5, 1, 5, 3], 3) == [5, 5, 3]
    assert largest_amounts([1, 2], 5) == [2, 1]
    assert largest_amounts([1, 2], 0) == []
    rng = random.Random(0)
    for _ in range(100):
        values = [rng.randint(0, 20) for _ in range(rng.randint(0, 15))]
        n = rng.randint(0, 6)
        assert largest_amounts(values, n) == sorted(values, reverse=True)[:n]
