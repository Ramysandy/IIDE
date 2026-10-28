"""Pure-helper behaviour (agent-visible; no telemetry involved)."""

import random

from app.formatting import file_response, largest_sizes, summarize_sizes


def test_file_response_shape():
    assert file_response("synthetic-file-1", "synthetic-user-owner") == {
        "file_id": "synthetic-file-1",
        "owner_id": "synthetic-user-owner",
    }


def test_summarize_sizes():
    assert summarize_sizes([]) == {"total_bytes": 0, "count": 0}
    assert summarize_sizes([10, 20, 0]) == {"total_bytes": 30, "count": 3}


def test_largest_sizes_matches_sorted_reference():
    assert largest_sizes([], 3) == []
    assert largest_sizes([5, 1, 5, 3], 3) == [5, 5, 3]
    assert largest_sizes([1, 2], 0) == []
    rng = random.Random(0)
    for _ in range(100):
        values = [rng.randint(0, 20) for _ in range(rng.randint(0, 15))]
        n = rng.randint(0, 6)
        assert largest_sizes(values, n) == sorted(values, reverse=True)[:n]
