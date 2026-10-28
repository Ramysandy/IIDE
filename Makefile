PY ?= .venv/bin/python
TESTBED ?= billing_api

.PHONY: install lint test test-fast testbed-test testbed-validate baseline

install:
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

lint:
	$(PY) -m ruff check .

# Project tests (unit + integration) and the testbed's own functional tests.
# They run as separate pytest invocations because every testbed exposes a
# top-level package called `app`.
test:
	$(PY) -m pytest
	$(PY) -m pytest testbeds/$(TESTBED)

test-fast:
	$(PY) -m pytest -m "not integration"

testbed-test:
	$(PY) -m pytest testbeds/$(TESTBED)

# Loads the testbed and cross-validates catalog, attacks, rules and mapping.
testbed-validate:
	$(PY) scripts/validate_testbed.py --testbed $(TESTBED)

# Writes testbeds/$(TESTBED)/baseline/* (k replays per attack plus a 30-replay flake
# calibration). Refuses to overwrite existing artifacts; add FORCE=--force to redo.
baseline:
	$(PY) scripts/run_baseline.py --testbed $(TESTBED) --calibrate 30 $(FORCE)
