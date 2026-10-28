"""Functional tests for sessions, roles, invoices, export, rate limit and webhooks."""

from __future__ import annotations

import pytest

INV = "synthetic-invoice-"


# ------------------------------------------------------------------ sessions


def test_calls_without_a_session_are_rejected(api):
    assert api.client.get(f"/invoices/{INV}1").status_code == 401
    assert api.client.get(f"/invoices/{INV}1", headers={"X-Session-Id": "nope"}).status_code == 401


def test_a_session_cannot_be_used_from_another_client(api):
    headers = api.session(3, "synthetic-client-victim")
    stolen = {**headers, "X-Client-Id": "synthetic-client-other"}
    assert api.client.get(f"/invoices/{INV}1", headers=headers).status_code == 200
    assert api.client.get(f"/invoices/{INV}1", headers=stolen).status_code == 401


# ------------------------------------------------------------------- invoices


def test_invoice_read_returns_fixture_data(api):
    response = api.client.get(f"/invoices/{INV}3", headers=api.session(3))
    assert response.status_code == 200
    assert response.json() == {"invoice_id": f"{INV}3", "amount_cents": 3000}


def test_unknown_invoice_is_404(api):
    assert api.client.get(f"/invoices/{INV}999", headers=api.session(3)).status_code == 404


# --------------------------------------------------------------------- export


def _export(api, headers, ids):
    return api.client.post("/invoices/export", json={"invoice_ids": ids}, headers=headers)


def test_analyst_can_export_and_totals_are_correct(api):
    response = _export(api, api.session(2), [f"{INV}1", f"{INV}2"])
    assert response.status_code == 200
    assert response.json()["record_count"] == 2 and response.json()["total_cents"] == 3000


def test_viewer_cannot_export(api):
    assert _export(api, api.session(3), [f"{INV}1"]).status_code == 403


def test_export_of_unknown_invoice_is_404(api):
    assert _export(api, api.session(2), [f"{INV}1", f"{INV}999"]).status_code == 404


def test_export_is_rate_limited_per_client(api):
    headers = api.session(2, "synthetic-client-a")
    assert [_export(api, headers, [f"{INV}1"]).status_code for _ in range(5)] == [200] * 3 + [
        429
    ] * 2
    other = api.session(2, "synthetic-client-b")
    assert _export(api, other, [f"{INV}1"]).status_code == 200  # limit is per client


@pytest.mark.parametrize("payload", [{}, {"invoice_ids": []}, {"invoice_ids": ["x"] * 51}])
def test_export_validates_input(api, payload):
    response = api.client.post("/invoices/export", json=payload, headers=api.session(2))
    assert response.status_code == 422


# ---------------------------------------------------------------------- roles


def _set_role(api, headers, target, role):
    return api.client.post(
        "/roles",
        json={"target_account_id": f"synthetic-account-{target}", "new_role": role},
        headers=headers,
    )


def test_admin_can_change_a_role_and_it_takes_effect(api):
    admin = api.session(1)
    viewer = api.session(3)
    assert _export(api, viewer, [f"{INV}1"]).status_code == 403
    response = _set_role(api, admin, 3, "analyst")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "previous_role": "viewer", "new_role": "analyst"}
    assert _export(api, viewer, [f"{INV}1"]).status_code == 200


def test_non_admin_cannot_change_roles(api):
    assert _set_role(api, api.session(2), 3, "admin").status_code == 403


def test_role_change_for_unknown_account_is_404(api):
    response = api.client.post(
        "/roles",
        json={"target_account_id": "synthetic-account-404", "new_role": "viewer"},
        headers=api.session(1),
    )
    assert response.status_code == 404


def test_invalid_role_name_is_422(api):
    response = api.client.post(
        "/roles",
        json={"target_account_id": "synthetic-account-3", "new_role": "root"},
        headers=api.session(1),
    )
    assert response.status_code == 422


# ------------------------------------------------------------------- webhooks


def test_admin_can_configure_the_webhook_and_external_targets_are_flagged(api):
    admin = api.session(1)
    internal = api.client.post(
        "/webhooks", json={"target_label": "synthetic-internal-other"}, headers=admin
    )
    external = api.client.post(
        "/webhooks", json={"target_label": "synthetic-external-collector"}, headers=admin
    )
    assert internal.json() == {"status": "ok", "external": False}
    assert external.json() == {"status": "ok", "external": True}


def test_non_admin_cannot_configure_the_webhook(api):
    response = api.client.post(
        "/webhooks", json={"target_label": "synthetic-internal-x"}, headers=api.session(2)
    )
    assert response.status_code == 403


def test_unreachable_webhook_does_not_break_the_operation_it_notifies(api):
    admin = api.session(1)
    api.client.post(
        "/webhooks", json={"target_label": "synthetic-internal-unreachable"}, headers=admin
    )
    assert _set_role(api, admin, 3, "analyst").status_code == 200
