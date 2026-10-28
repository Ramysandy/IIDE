"""Emulation that never finishes in time (used with a 1 s replay timeout)."""

import time


def emulate(client, *, correlation_id):
    time.sleep(60)
