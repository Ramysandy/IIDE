"""Fixed benign workload (negative control; later the NRG volume workload, spec 7.10).

Ordinary activity that stays below every frozen threshold. It must not fire any rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "attacks"))
from emu_common import ADMIN, OUTSIDER, OWNER, READER, get, post  # noqa: E402


def emulate(client, *, correlation_id: str) -> None:
    cid = correlation_id
    post(client, OWNER, "/files", cid, {"file_id": "synthetic-file-new-1", "size_bytes": 100})
    for _ in range(2):
        get(client, OWNER, "/files/synthetic-file-1", cid)
    for i in (1, 2, 3):
        get(client, READER, f"/files/synthetic-file-{i}", cid)
    for _ in range(2):  # two denials: below the probing threshold
        get(client, OUTSIDER, "/files/synthetic-file-1", cid)

    post(client, OWNER, "/files/synthetic-file-1/sharing", cid, {"visibility": "private"})

    approval = post(client, READER, "/approvals", cid, {"file_id": "synthetic-file-13"})
    approval_id = approval.json()["approval_id"]
    post(client, OWNER, f"/approvals/{approval_id}/decision", cid, {"decision": "approve"})
    get(client, READER, "/files/synthetic-file-13", cid)
    post(
        client, READER, "/files/export", cid, {"file_ids": ["synthetic-file-1", "synthetic-file-2"]}
    )

    post(client, ADMIN, "/webhook", cid, {"label": "synthetic-endpoint-unreachable"})
    post(
        client, OWNER, "/files/synthetic-file-2/sharing", cid, {"visibility": "private"}
    )  # 1 failure
    post(client, ADMIN, "/webhook", cid, {"label": "synthetic-endpoint-a"})

    for _ in range(2):  # two validation errors
        post(client, READER, "/files", cid, {})
