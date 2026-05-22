# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

stackai orchestrates parallel Claude Code agents in sandboxed Apple Containers (macOS 26+, ARM64). Each agent runs in its own git worktree for branch-isolated development. Two modes: direct container management (Makefile/CLI) and host-side skill coordination (spawn-agent).

## Build & run

```bash
# Build the production image (ARM64, Wolfi-based)
cd config && make build

# Create the container network (required once)
make network

# Interactive container session
make run

# Spawn a headless agent
make spawn BRANCH=feat/foo TASK="implement feature X"

# Monitor agents
make list-agents
make follow-agent BRANCH=feat/foo
make stop-agent BRANCH=feat/foo

# Cleanup
make clean          # remove image + containers
make clean-network  # remove bridge network
make clean-all      # remove everything
```

### Python CLI (`q` command)

```bash
cd app/cli && uv sync
uv run q build
uv run q spawn --branch feat/foo --task "implement feature X"
uv run q agents list
```

## Testing

```bash
# Python CLI tests (from app/cli/)
cd app/cli && uv sync
uv run pytest -v                    # full suite (unit + acceptance)
uv run pytest tests/test_agents.py  # single module
uv run pytest -k test_spawn         # single test by name

# Acceptance tests only (Gherkin/BDD, local — no real containers)
make acceptance-test

# End-to-end tests (real containers, opt-in, local-only — see docs/agents/e2e-tests.md)
make e2e-test

# Mutation testing gate (≥ 70% kill rate)
make mutation-ci-threshold

# Pre-PR quality gate: acceptance + skill evals
make local-qa

# Linting
uv run ruff check .

# Entrypoint BDD tests (from config/)
cd config && shellspec --shell bash
```

CI runs unit tests, mutation tests with a 70% threshold, hadolint on both Dockerfiles, and an Alpine builder stage compilation check. Acceptance tests run locally only — GitHub Actions does not have Apple Container CLI.

## Testing philosophy

### Acceptance tests — source of truth

The acceptance tests in `app/cli/tests/acceptance/features/` (Gherkin) define the contracted behaviour of the CLI. They invoke the public CLI surface via `CliRunner.invoke(app, [...])` with `run_make` mocked, so no real containers are spawned. Run them with `make acceptance-test`.

**Rule**: do not modify an acceptance test without explicit agreement. Every new feature starts with an acceptance test. Unit tests and implementation serve the acceptance contract — never the other way around.

### TDD flow (3 laws)

When implementing a feature or fixing a bug:

1. **Write the acceptance test** in Gherkin describing the expected behaviour from the user's perspective.
2. **Apply Robert Martin's three laws of TDD** at the unit level:
   - Law 1: Do not write production code without a failing unit test.
   - Law 2: Write no more of a unit test than is sufficient to fail (compilation failure counts).
   - Law 3: Write no more production code than is necessary to make the failing test pass.
3. **Repeat** the red → green → refactor cycle until the acceptance test passes.

Mutation tests (run via `make mutation-ci-threshold`) act as the safety net that catches semantic regressions the test suite would otherwise miss.

For skill evals (LLM-graded), see the **Skill evals** section below.

## Python code conventions (`app/cli/`)

The Python CLI follows the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html). Ruff (configured in `app/cli/pyproject.toml`) enforces the mechanical rules: line length 100, import order, pep8-naming, pydocstyle (Google convention), pyupgrade, bugbear, comprehensions (C4), simplify, return, pathlib, unused-args, eradicate, builtins, tidy-imports. Run `make apply-sensors` to auto-fix + verify the full quality pipeline (lint, unit tests, mutation gate).

The rules below cannot be enforced by Ruff and must be applied by hand:

- **Docstring content (Google sections)**: the first line is a one-sentence imperative summary. When parameters, return value, raised exceptions, or yielded items deserve documentation, use `Args:`, `Returns:`, `Raises:`, `Yields:` sections indented 4 spaces under the summary.
- **`TODO` markers**: always `TODO(@username):` or `TODO(#issue-id):` — never a bare `TODO`. The identifier makes ownership explicit and lets `git grep TODO` find actionable items.
- **`TYPE_CHECKING` imports**: imports used only inside type annotations go inside `if TYPE_CHECKING:` and are referenced as forward-reference strings. Avoid runtime cost for typing-only dependencies.
- **`assert` only in tests**: production code under `src/` must not rely on `assert` for control flow — `python -O` strips them. Raise specific exceptions instead (`raise ValueError(...)`, `raise typer.Exit(1)`).
- **Specific exceptions**: never `except Exception:` bare; catch the concrete types relevant to the operation (`subprocess.CalledProcessError`, `OSError`, `typer.Exit`).
- **`typer.echo` vs `logging`**: `typer.echo` is for user-facing CLI output only. Any diagnostic or trace information goes through `logger = logging.getLogger(__name__)`.
- **Naming semantics**: variable names must not shadow built-ins (`vars`, `id`, `type`, `list`, `dict`, `input`). Prefer descriptive names: `make_vars`, `env_overrides`, `image_tag`. Function names are imperative verbs in `snake_case`.
- **No mutable default arguments**: never `def f(x: list = []):`. Use `None` and materialise inside (`x = x if x is not None else []`).
- **Absolute imports**: inside `container_cli/` always import with the full package path (`from container_cli.utils import run_make`), never relative.
- **Function size**: revisit any function past ~25 lines and consider splitting; single responsibility per function.

## Architecture

- **`config/`** — Container infrastructure: `Dockerfile.wolfi` (production, multi-stage: Rust tool compilation → runtime with Claude CLI, Node, Python), `entrypoint.sh` (credential injection + worktree creation + su-exec privilege drop), `Makefile` (orchestration)
- **`app/cli/`** — Python CLI (`q`) using Typer+Rich that wraps Makefile targets. Entry point registered as `q` in pyproject.toml. Commands delegate to `make` via `utils.run_make()`
- **`.claude/skills/`** — Host-side Claude Code skills for multi-agent orchestration (spawn-agent, spawn-agent-workspace)
- **`docs/agents/`** — All project documentation (container reference, CLI, setup/auth, skill architecture, evals)

### Key concepts

- **Dual-token architecture**: Host uses `CLAUDE_CONTAINER_OAUTH_TOKEN`; inside the container it maps to `CLAUDE_CODE_OAUTH_TOKEN`. Host credentials are mounted read-only and copied (never modified in place).
- **Worktree isolation**: Each agent gets its own git worktree under `$AGENTS_HOME` (default: sibling `.worktrees/` directory). Branches are merge-ready when the agent finishes.
- **Apple Container CLI**: This project uses Apple's container runtime, not Docker. The Makefile targets use `container` commands.

## Documentation

When implementing a new feature, always update the relevant documentation in `docs/`.

- If the feature affects container behavior, image build, or the entrypoint: update `docs/agents/container-agent.md`
- If the feature affects how agents are spawned or monitored: update `docs/agents/spawn-agent-skill.md`
- If the feature adds or changes CLI commands in `app/cli/`: update `docs/agents/cli.md`
- If a new subsystem is introduced with no existing doc, create a new file under the appropriate `docs/` subdirectory

Documentation should reflect the current state of the code. Keep troubleshooting tables and flow descriptions in sync with the actual implementation.

## Skill evals

When modifying any skill under `.claude/skills/`, run its evals locally before considering the change complete. Evals verify that the skill still produces correct outputs across all test scenarios.

```
/skill-creator:skill-creator run evals for the <skill-name> skill at ~/.claude/skills/<skill-name>/
```

See `docs/agents/evals.md` for full details on prerequisites, how to add new evals, and how to interpret results.
