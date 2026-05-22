# Makefile for Python CLI mutation testing

.PHONY: mutation-run mutation-show mutation-results mutation-run-file mutation-clean

# Run the full mutation suite
mutation-run:
	uv run mutmut run

# Display mutation results/diffs
mutation-show:
	uv run mutmut show

# Show mutation score summary
mutation-results:
	uv run mutmut results

# Run mutations on a specific file
# Usage: make mutation-run-file FILE=path/to/file.py
mutation-run-file:
	uv run mutmut run --paths-to-mutate $(FILE)

# Reset the mutmut state/cache and remove generated artifacts
mutation-clean:
	rm -rf mutants/ .mutmut-cache

# CI gate: run mutations and fail if kill rate < 70%
.PHONY: mutation-ci-threshold
mutation-ci-threshold: mutation-run
	@uv run mutmut export-cicd-stats >/dev/null
	@uv run python -c 'import json,sys; d=json.load(open("mutants/mutmut-cicd-stats.json")); k,t=d["killed"],d["total"]; s=k/t if t else 0; print(f"Mutation score: {s:.1%} ({k}/{t})"); sys.exit(0 if s>=0.70 else 1)'

# Acceptance tests (Gherkin/BDD) — local only, GitHub Actions lacks Apple Container CLI
.PHONY: acceptance-test test-all eval-skills local-qa
acceptance-test:
	uv run pytest tests/acceptance -v

# Full local test suite: unit + acceptance
test-all:
	uv run pytest tests tests/acceptance -v

# Skill evals via Claude Code CLI (currently only spawn-agent)
eval-skills:
	claude -p "/skill-creator:skill-creator run evals for the spawn-agent skill at ~/.claude/skills/spawn-agent/"

# End-to-end container tests — opt-in, local-only (needs Apple Container CLI).
# Spawns real agent containers; the Claude round-trip spends Claude credits.
# Excluded from CI and from `local-qa` by design.
.PHONY: e2e-test
e2e-test:
	STACKAI_E2E=1 uv run pytest tests/e2e -v -m e2e

# Pre-PR quality gate
local-qa: acceptance-test eval-skills

# Quality sensors: lint + format + unit tests + mutation gate (no acceptance)
.PHONY: lint unit-test apply-sensors

lint:
	uv run ruff check --fix .
	uv run ruff format .

unit-test:
	uv run pytest tests --ignore=tests/acceptance -v

apply-sensors: lint unit-test mutation-ci-threshold
	@echo "[apply-sensors] OK — lint clean, unit tests green, mutation >= 70%"
