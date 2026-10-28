"""Benign traffic used as negative controls: must never fire the brute-force rule."""

PASS_9 = "synthetic-fixture-passphrase-9"


def _post(client, correlation_id, account, passphrase):
    return client.post(
        "/login",
        json={
            "client_id": "synthetic-client-benign",
            "account_id": account,
            "passphrase": passphrase,
        },
        headers={"X-Correlation-ID": correlation_id},
    )


def emulate(client, *, correlation_id):
    # Typos followed by success, repeated, never reaching the lockout threshold.
    for _ in range(3):
        for _ in range(4):
            _post(client, correlation_id, "synthetic-account-9", "synthetic-typo")
        _post(client, correlation_id, "synthetic-account-9", PASS_9)
    # Failures spread across different accounts: no single account crosses the threshold.
    for _ in range(3):
        _post(client, correlation_id, "synthetic-account-9", "synthetic-typo")
        _post(client, correlation_id, "synthetic-account-10", "synthetic-typo")
