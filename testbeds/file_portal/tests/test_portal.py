"""Functional tests for the file portal (product behaviour only)."""

from __future__ import annotations

import pytest
from conftest import ADMIN, OUTSIDER, OWNER, READER

# ---------------------------------------------------------------------- files


def test_upload_creates_a_private_file_owned_by_the_uploader(api):
    response = api.post(READER, "/files", file_id="synthetic-file-new", size_bytes=10)
    assert response.status_code == 201
    assert api.client.get("/files/synthetic-file-new", headers=api.h(READER)).status_code == 200
    assert api.client.get("/files/synthetic-file-new", headers=api.h(OUTSIDER)).status_code == 403


def test_duplicate_upload_is_a_conflict(api):
    assert api.post(OWNER, "/files", file_id="synthetic-file-1", size_bytes=1).status_code == 409


def test_owner_and_shared_reader_can_read_but_outsider_cannot(api):
    assert api.read(OWNER, 1).status_code == 200
    assert api.read(READER, 1).status_code == 200
    assert api.read(OUTSIDER, 1).status_code == 403


def test_reader_cannot_read_unshared_files(api):
    assert api.read(READER, 13).status_code == 403


def test_unknown_file_is_404(api):
    assert api.read(OWNER, 999).status_code == 404


@pytest.mark.parametrize("size", [-1, 10_000_001])
def test_upload_validates_size(api, size):
    assert api.post(OWNER, "/files", file_id="x", size_bytes=size).status_code == 422


# --------------------------------------------------------------------- export


def test_export_succeeds_for_readable_files(api):
    response = api.post(
        READER, "/files/export", file_ids=[f"synthetic-file-{i}" for i in range(1, 13)]
    )
    assert response.status_code == 200 and response.json()["file_count"] == 12


def test_export_fails_if_any_file_is_unreadable(api):
    response = api.post(READER, "/files/export", file_ids=["synthetic-file-1", "synthetic-file-13"])
    assert response.status_code == 403


def test_export_of_unknown_file_is_404(api):
    assert (
        api.post(READER, "/files/export", file_ids=["synthetic-file-1", "nope"]).status_code == 404
    )


@pytest.mark.parametrize("payload", [{}, {"file_ids": []}, {"file_ids": ["x"] * 51}])
def test_export_validates_input(api, payload):
    assert api.client.post("/files/export", json=payload, headers=api.h(READER)).status_code == 422


# -------------------------------------------------------------------- sharing


def test_owner_can_make_a_file_public_and_everyone_can_then_read_it(api):
    assert api.read(OUTSIDER, 13).status_code == 403
    response = api.post(OWNER, "/files/synthetic-file-13/sharing", visibility="public")
    assert response.status_code == 200 and response.json()["previous_visibility"] == "private"
    assert api.read(OUTSIDER, 13).status_code == 200


def test_making_a_file_private_again_revokes_public_access(api):
    api.post(OWNER, "/files/synthetic-file-13/sharing", visibility="public")
    api.post(OWNER, "/files/synthetic-file-13/sharing", visibility="private")
    assert api.read(OUTSIDER, 13).status_code == 403


def test_only_the_owner_can_change_sharing(api):
    response = api.post(READER, "/files/synthetic-file-1/sharing", visibility="public")
    assert response.status_code == 403
    assert api.read(OUTSIDER, 1).status_code == 403


def test_sharing_validates_visibility_and_file(api):
    assert api.post(OWNER, "/files/synthetic-file-1/sharing", visibility="world").status_code == 422
    assert api.post(OWNER, "/files/nope/sharing", visibility="public").status_code == 404


# ------------------------------------------------------------------ approvals


def test_owner_approval_grants_the_requester_access(api):
    assert api.read(OUTSIDER, 13).status_code == 403
    approval = api.post(OUTSIDER, "/approvals", file_id="synthetic-file-13").json()["approval_id"]
    decision = api.post(OWNER, f"/approvals/{approval}/decision", decision="approve")
    assert decision.status_code == 200 and decision.json()["self_approved"] is False
    assert api.read(OUTSIDER, 13).status_code == 200


def test_rejection_does_not_grant_access(api):
    approval = api.post(OUTSIDER, "/approvals", file_id="synthetic-file-13").json()["approval_id"]
    api.post(OWNER, f"/approvals/{approval}/decision", decision="reject")
    assert api.read(OUTSIDER, 13).status_code == 403


def test_a_decision_can_only_be_made_once(api):
    approval = api.post(OUTSIDER, "/approvals", file_id="synthetic-file-13").json()["approval_id"]
    assert api.post(OWNER, f"/approvals/{approval}/decision", decision="reject").status_code == 200
    assert api.post(OWNER, f"/approvals/{approval}/decision", decision="approve").status_code == 409


def test_only_owner_or_admin_can_decide(api):
    approval = api.post(OUTSIDER, "/approvals", file_id="synthetic-file-13").json()["approval_id"]
    assert (
        api.post(READER, f"/approvals/{approval}/decision", decision="approve").status_code == 403
    )


def test_admin_may_approve_their_own_request_and_it_is_flagged(api):
    approval = api.post(ADMIN, "/approvals", file_id="synthetic-file-13").json()["approval_id"]
    response = api.post(ADMIN, f"/approvals/{approval}/decision", decision="approve")
    assert response.status_code == 200 and response.json()["self_approved"] is True


def test_approval_edge_cases(api):
    assert api.post(READER, "/approvals", file_id="nope").status_code == 404
    assert api.post(OWNER, "/approvals/nope/decision", decision="approve").status_code == 404
    assert api.post(OWNER, "/approvals/x/decision", decision="maybe").status_code == 422


# -------------------------------------------------------------------- webhook


def test_only_admin_can_configure_the_webhook(api):
    assert api.post(OWNER, "/webhook", label="synthetic-endpoint-b").status_code == 403
    assert api.post(ADMIN, "/webhook", label="synthetic-endpoint-b").status_code == 200


def test_unreachable_webhook_does_not_break_the_operation_it_notifies(api):
    api.post(ADMIN, "/webhook", label="synthetic-endpoint-unreachable")
    response = api.post(OWNER, "/files/synthetic-file-13/sharing", visibility="private")
    assert response.status_code == 200
