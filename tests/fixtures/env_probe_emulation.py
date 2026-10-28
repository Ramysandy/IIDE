"""Fails if the parent's secret-looking environment leaked into the replay process."""

import os


def emulate(client, *, correlation_id):
    leaked = [k for k in os.environ if k.startswith("IIDE_TEST_SECRET")]
    if leaked:
        raise RuntimeError(f"environment leaked into replay process: {leaked}")
