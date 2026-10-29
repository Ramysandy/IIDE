PY ?= .venv/bin/python
TESTBED ?= billing_api
TESTBEDS ?= billing_api file_portal

.PHONY: install lint test test-fast testbed-test testbed-validate baseline baseline-all score manifest-pilot run-pilot score-runs score-matched compare-baselines compare-live g2-agreement report export-reviews

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

# 144-run pilot (spec 11.4 / 16). DRY_RUN=1 validates the manifest and prints the plan
# without calling any agent. A real run is refused while required gates are open,
# agents are unconfigured, or instructions are DRAFT_UNREVIEWED.
manifest-pilot:
	$(PY) scripts/run_pilot.py --manifest-only

run-pilot:
	$(PY) scripts/run_pilot.py $(if $(filter 1,$(DRY_RUN)),--dry-run,) $(PILOT_EXTRA)

score-runs:
	$(PY) scripts/score_runs.py

# IAE/IIF/SR/DG on one matched wording triple. n=1: no bootstrap CIs. Not a 144-run.
score-matched:
	$(PY) scripts/score_matched_group.py

# Spec 15 / G4 construct check on four scripted patches. Default never calls an LLM.
# WITH_LLM=1 calls Cohere on the four diffs if COHERE_API_KEY is set (writes g4_llm_reviewer).
compare-baselines:
	$(PY) scripts/compare_baselines.py $(if $(filter 1,$(WITH_LLM)),--with-llm,)

# G4 on live F1 composer diffs vs oracle y. Never calls an LLM. Not a 144-run.
compare-live:
	$(PY) scripts/compare_live.py

# G2 kappa on docs/g2 annotator files. Exits 2 if annotator_b.yaml is incomplete. Does not set gates.yaml.
g2-agreement:
	$(PY) scripts/score_g2.py

# Spec 16 harness check. Writes pre_pilot_status.{md,json}. Exit 1 on hash drift.
# The paper-facing pilot report is experiments/reports/pilot_report.md (not 144).
report:
	$(PY) scripts/verify_reproducibility.py
	@echo "Harness check: experiments/reports/pre_pilot_status.md"
	@echo "Pilot report (F1 composer seed-1, not 144): experiments/reports/pilot_report.md"

# Blinded A2 worksheets for S_sec, criticality, and instructions. Does not fill B or set REVIEWED.
export-reviews:
	$(PY) scripts/export_review_packs.py
