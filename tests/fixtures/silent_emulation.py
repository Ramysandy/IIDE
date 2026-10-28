"""Valid replay that produces no telemetry at all (an honest 'silent' outcome)."""


def emulate(client, *, correlation_id):
    return None
