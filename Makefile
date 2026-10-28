PY ?= .venv/bin/python
TESTBED ?= billing_api
TESTBEDS ?= billing_api file_portal

.PHONY: install lint test test-fast testbed-test testbed-validate baseline baseline-all score

install:
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"

lint:
	$(PY) -m ruff check .

# Project tests (unit + integration), then each testbed's own functional tests.
# They run as separate pytest invocations because every testbed exposes a
# top-level package called `app`.
test:
	$(PY) -m pytest
	for tb in $(TESTBEDS); do $(PY) -m pytest testbeds/$$tb -p no:cacheprovider || exit 1; done

test-fast:
	$(PY) -m pytest -m "not integration"

testbed-test:
	$(PY) -m pytest testbeds/$(TESTBED) -p no:cacheprovider

# Loads the testbed and cross-validates catalog, attacks, rules, mapping and benign workload.
testbed-validate:
	for tb in $(TESTBEDS); do $(PY) scripts/validate_testbed.py --testbed $$tb || exit 1; done

# Writes testbeds/$(TESTBED)/baseline/* (k replays per attack, a benign negative control and
# a per-attack flake calibration). Refuses to overwrite existing artifacts; FORCE=--force
# re-records, which is only legitimate under a new experiment_version.
baseline:
	$(PY) scripts/run_baseline.py --testbed $(TESTBED) $(FORCE)

baseline-all:
	for tb in $(TESTBEDS); do $(PY) scripts/run_baseline.py --testbed $$tb $(FORCE) || exit 1; done

# Score a replay ledger against the baseline (default: baseline self-comparison check).
score:
	$(PY) scripts/score_replays.py --testbed $(TESTBED)
