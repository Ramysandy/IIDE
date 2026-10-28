"""Emulation that crashes: the replay must be invalid, never counted as 'silent'."""


def emulate(client, *, correlation_id):
    raise RuntimeError("synthetic crash for harness error-handling test")
