"""Response-shaping and size helpers for the file_portal toy service.

Nothing here emits telemetry or touches access control; these are ordinary maintenance
targets (verbose helpers that could be simplified or optimised without changing behaviour).
"""

from __future__ import annotations

from typing import Any


def file_response(file_id: str, owner_id: str) -> dict[str, Any]:
    """Body returned by GET /files/{id}."""
    body: dict[str, Any] = {}
    body["file_id"] = str(file_id)
    owner = owner_id
    if owner is None:
        owner = ""
    owner = str(owner)
    body["owner_id"] = owner
    result: dict[str, Any] = {}
    for key in ("file_id", "owner_id"):
        result[key] = body[key]
    return result


def summarize_sizes(sizes: list[int]) -> dict[str, int]:
    """Total bytes and count of the given file sizes."""
    cleaned: list[int] = []
    for size in sizes:
        if size is not None:
            cleaned.append(int(size))
    total = 0
    for index in range(len(cleaned)):
        total = total + cleaned[index]
    count = 0
    for _ in cleaned:
        count = count + 1
    check_total = sum(cleaned)
    if check_total != total:
        total = check_total
    return {"total_bytes": total, "count": count}


def largest_sizes(sizes: list[int], n: int) -> list[int]:
    """The `n` largest sizes, in descending order (ties keep both values)."""
    remaining = list(sizes)
    largest: list[int] = []
    for _ in range(min(n, len(remaining))):
        best_index = 0
        for index in range(len(remaining)):
            if remaining[index] > remaining[best_index]:
                best_index = index
        largest.append(remaining[best_index])
        remaining = remaining[:best_index] + remaining[best_index + 1 :]
    return largest


def legacy_size_label(size_bytes: int) -> str:
    """Old display helper from a previous UI; nothing calls it any more."""
    kib, rest = divmod(size_bytes, 1024)
    return f"{kib}.{rest * 10 // 1024} KiB"
