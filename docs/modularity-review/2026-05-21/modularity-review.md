# Modularity Review

**Scope**: The `q` Python CLI (`app/cli/`) and its integration boundary with `config/Makefile`
**Date**: 2026-05-21

## Executive Summary

stackai orchestrates parallel Claude Code agents in sandboxed Apple Containers; the `q` CLI is a typed Typer front end that wraps the `config/Makefile` orchestration targets. In the small the CLI is healthy — `utils.run_make` cleanly encapsulates the *mechanism* of invoking `make`, and every module is short and single-purpose. The [modularity](https://coupling.dev/posts/core-concepts/modularity/) weakness is concentrated at one boundary: the CLI's knowledge of *which* Makefile targets exist and *what variables they accept* is [functionally coupled](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) and **implicit** — encoded as bare string literals scattered across five command modules with no contract to make the dependency explicit or fail loudly. Because the Makefile is the [core subdomain](https://coupling.dev/posts/dimensions-of-coupling/volatility/) of the product and evolves continuously, this is the most important finding: the CLI silently breaks at runtime when a target is renamed. A second, self-inflicted issue compounds it — the `status` command reaches *past* the Makefile into the container's private `.agent/status.json` file, reproducing an existing `status-agent` target with [intrusive coupling](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/).

Overall status: **needs attention**. There is no critical distributed-monolith failure, but two unbalanced-and-volatile integrations will cause avoidable pain as the Makefile evolves, and two smaller cohesion defects add cognitive friction.

## Coupling Overview

| Integration | [Strength](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) | [Distance](https://coupling.dev/posts/dimensions-of-coupling/distance/) | [Volatility](https://coupling.dev/posts/dimensions-of-coupling/volatility/) | [Balanced?](https://coupling.dev/posts/core-concepts/balance/) |
| --- | --- | --- | --- | --- |
| `commands/*` → `config/Makefile` (target & variable names) | [Functional](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/), implicit | High — separate language, separate directory, subprocess | High — orchestration is the core subdomain, targets evolve | **No** — unbalanced & volatile |
| `agents.status` / `pi.status` → container `.agent/status.json` | [Intrusive](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) | High — bash entrypoint, runs inside the container | Medium–High — monitoring actively developed | **No** — unbalanced & volatile |
| `agents._agents_home` ≡ `pi_agents._agents_home` | [Functional](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/), duplicated | Low — sibling modules, one package | Low–Medium | **No** — duplication mistaken for cohesion |
| `_agents_home()` fallback ≡ Makefile `AGENTS_HOME` | [Functional](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/), duplicated | High — cross-language | Low | Tolerable — low volatility neutralizes |
| `main.py` → `commands/*` (registration) | [Model](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/), inconsistent | Low — one package | Low | Borderline — low cohesion |
| `check_token()` ≡ Makefile `_check-token` | [Functional](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/), duplicated | High — cross-language | Low | Yes — low volatility neutralizes |

The last row is included deliberately as a contrast: it *is* duplicated, unbalanced coupling, but [volatility](https://coupling.dev/posts/dimensions-of-coupling/volatility/) is low enough that the [balance rule](https://coupling.dev/posts/core-concepts/balance/) — `(STRENGTH XOR DISTANCE) OR NOT VOLATILE` — is satisfied. Not every imbalance is a defect; only the volatile ones below are.

## Issue: Makefile interface is an implicit, scattered contract

**Integration**: `container_cli/commands/*` → `config/Makefile`
**Severity**: Significant

### Knowledge Leakage

Every command function knows, as hard-coded strings, two things about the Makefile: the **name of a target** (`"spawn"`, `"list-agents"`, `"spawn-pi"`, `"summary-agent"`, …) and the **names of the variables that target accepts** (`BRANCH`, `TASK`, `CPUS`, `MEMORY`, `IMAGE`, `DOCKERFILE`, `SUBNET`, `NETWORK`, `PI_IMAGE`, `PI_DOCKERFILE`, `PI_BASE_URL`, `PI_MODEL_ID`, `NAME`). That is the Makefile's *functional requirements* — what it does and how it must be invoked — replicated inside Python. The shared knowledge is **implicit**: there is no enum, no schema, no generated mapping. The only place the correspondence is written down is a prose table in `docs/agents/cli.md`, which nothing keeps honest. `run_make` centralizes the *mechanism* (`make -C config <target> KEY=VALUE`) but not the *vocabulary*, so each of the five `commands/*` modules independently owns a fragment of an undeclared contract.

This is [functional coupling](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) — the components must change together when a target's interface changes — and it is implicit functional coupling, which the model singles out as particularly dangerous: there is no compiler, type checker, or test that links `agents.py:33`'s `"BRANCH"` to the Makefile's `BRANCH ?=`.

### Complexity Impact

A developer changing a Makefile target name or variable cannot see, *from the Makefile*, that Python depends on it — the dependency is invisible at the point of change. To safely rename one target the developer must simultaneously hold in mind: the Makefile target, the `run_make` call site in `commands/*`, the `cli.md` mapping table, and the acceptance test. That is knowledge spread across four artifacts in two languages for what should be a trivial rename. It exceeds the 4±1 working-memory budget, which is precisely what turns a change from [modular](https://coupling.dev/posts/core-concepts/modularity/) (predictable outcome) into [complex](https://coupling.dev/posts/core-concepts/complexity/) (outcome discovered only by running it).

### Cascading Changes

- **Renaming `list-agents` → `agents-list` in the Makefile**: the Python literal `"list-agents"` still type-checks, still passes `ruff`, still imports cleanly. The break surfaces only when a user runs `q agents list` and `make` reports `No rule to make target`. The acceptance tests mock `run_make`, so they assert *which string was passed*, not that the target *exists* — there is no test-time signal either.
- **Adding a variable to an existing target** (e.g. a `--no-cache` option for `build`): requires coordinated edits in `build.py`, the Makefile, and `cli.md`, with nothing enforcing that the three agree.
- The coupling is genuinely [tight](https://coupling.dev/posts/core-concepts/balance/): high [integration strength](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) (functional) across high [distance](https://coupling.dev/posts/dimensions-of-coupling/distance/) — separate language, separate top-level directory, subprocess boundary. The Makefile is a [core subdomain](https://coupling.dev/posts/dimensions-of-coupling/volatility/): the orchestration logic *is* the product, and git history shows targets added continuously (PI agents, `apply-sensors`). High strength + high distance + high [volatility](https://coupling.dev/posts/dimensions-of-coupling/volatility/) fails the balance rule.

Why **Significant** and not Critical: the same person maintains both sides, so [socio-technical distance](https://coupling.dev/posts/dimensions-of-coupling/distance/) is low — there is no cross-team coordination cost — and Makefile change is mostly *additive* (new targets), so existing literals rarely break. The danger is real but not yet frequent.

### Recommended Improvement

Introduce a single [contract](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) module — e.g. `container_cli/makefile.py` — as the *only* place target names and their permitted variables are written down. One small structure per target (target name + allowed variable keys) converts the implicit functional coupling into explicit [contract coupling](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) localized in one file; command modules then reference `Targets.SPAWN` instead of the literal `"spawn"`. Optionally add one test that runs `make -C config -n <target>` (dry-run) for every target in the registry, so a renamed or removed target fails CI instead of a user's terminal.

This deliberately does **not** reduce distance — the CLI must wrap the Makefile, that is its purpose, and decomposing further would only raise distance. It reduces *strength* by encapsulating the contract, and it concentrates the volatile knowledge so a Makefile change has exactly one Python counterpart to update. Trade-off: a thin indirection layer plus the discipline of keeping the registry current — cheap relative to silent runtime breakage in the product's most-changed area.

## Issue: `status` command bypasses the Makefile and reads the container's private file

**Integration**: `agents.status` / `pi_agents.status` → container worktree `.agent/status.json`
**Severity**: Significant

### Knowledge Leakage

`agents.py:78` and `pi_agents.py:128` build the path `$AGENTS_HOME/<branch>/.agent/status.json` and read it directly off disk. `.agent/` is internal bookkeeping created by the container entrypoint (`config/entrypoint.sh` / `entrypoint-pi.sh`) for its own use; the CLI treats that private layout as if it were a public interface. This is [intrusive coupling](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) — the highest [integration strength](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) — because the CLI depends on an implementation detail of a different component.

The leak is twofold: the *directory layout* (`.agent/status.json`) and even the *fallback message text* (`[status] No status file found…`, `[status] Expected at: …`) are reproduced in Python. They are reproduced because the Makefile **already has** a `status-agent` target (`Makefile:179`) that performs the identical read and prints near-identical messages. So this is also [functional coupling](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) through duplication — the knowledge is copied, not shared.

### Complexity Impact

There are now two implementations of "show agent status" — `status-agent` in Make and `status()` in Python — and nothing keeps them consistent. `q agents summary` routes through `make summary-agent`, but `q agents status` does *not* route through `make status-agent`; a reader cannot predict from the CLI surface which commands delegate and which reimplement. The Python file read looks like ordinary I/O, not an integration point, so it is easy to miss when reasoning about what depends on the entrypoint's layout — the integration is hidden, which is the hallmark of [complexity](https://coupling.dev/posts/core-concepts/complexity/).

### Cascading Changes

- **The entrypoint relocates `status.json`** (say to `.agent/state/status.json`): `status-agent`, `status-pi-agent`, `agents.status`, and `pi_agents.status` all break — four sites, two languages — and the two Python ones give no signal until invoked.
- **The "no status file" UX is reworded in the Makefile only**: `q … status` silently keeps the old wording; the two surfaces drift apart.
- `status.json` is part of actively-developed structured monitoring (recent commits #7 and #9), so this sits in a [volatile](https://coupling.dev/posts/dimensions-of-coupling/volatility/) area — the duplication *will* be exercised. Intrusive strength + high distance + volatility is unbalanced and not neutralized.

### Recommended Improvement

Route `status` through the target that already exists: `run_make("status-agent", {"BRANCH": branch})` — exactly as `summary` already does. This removes the intrusive coupling *and* the duplication in one move: the Makefile becomes the single component that knows the `.agent/` layout, and the CLI holds only a target name (governed by the contract module proposed in the first issue). The documented rationale for the direct read — "works after the container has exited" — is *already* satisfied by `status-agent`, which is a pure file read with no live-container dependency, so no capability is lost.

Trade-off: the Python `status` currently raises `typer.Exit(1)` when the file is missing, whereas the Makefile target prints a message and exits `0`. If a non-zero exit code is contractually required, add an explicit `exit 1` to the missing-file branch of `status-agent` rather than reimplementing the read in Python. The cost is one line of Make; the gain is eliminating an intrusive, duplicated integration in a volatile area.

## Issue: Worktree-path logic duplicated across command modules

**Integration**: `agents._agents_home` ≡ `pi_agents._agents_home` (and both ≡ Makefile `AGENTS_HOME`)
**Severity**: Minor

### Knowledge Leakage

`_agents_home()` is byte-for-byte identical in `agents.py:15` and `pi_agents.py:25`: "use `$AGENTS_HOME` if set, else `<git-root>/../.worktrees`". The same rule is the Makefile's `AGENTS_HOME ?= $(dirname GIT_ROOT)/.worktrees` (`Makefile:54`). One business rule — where agent worktrees live — implemented three times. This is [functional coupling](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) through duplicated knowledge. The `run`/`shell` pair in `run.py` is a smaller instance of the same pattern: two functions with identical bodies that differ only in the target string passed to `run_make`.

### Complexity Impact

The two Python copies sit at low [distance](https://coupling.dev/posts/dimensions-of-coupling/distance/) — sibling modules in one package. High strength at low distance would normally read as [high cohesion](https://coupling.dev/posts/core-concepts/balance/), which is modular. But this is duplication, not cohesion: the copies are not one deliberate unit, they are two units that *secretly* share a rule. The `STRENGTH XOR DISTANCE` formula says "balanced" only if you mistake the duplication for cohesion. The real cost is the hidden obligation every developer carries — to remember that editing one copy means editing the twin.

### Cascading Changes

- **Changing the fallback** (e.g. `.worktrees` → `.agent-worktrees`) requires editing both Python copies; missing one makes `q agents …` and `q pi …` resolve *different* worktree roots — a confusing, hard-to-spot bug.
- The Python ↔ Makefile copy is unbalanced (high strength, high cross-language distance), but [volatility](https://coupling.dev/posts/dimensions-of-coupling/volatility/) is low — the worktree convention rarely changes. By the [balance rule](https://coupling.dev/posts/core-concepts/balance/), low volatility neutralizes it: tolerable [technical debt](https://coupling.dev/posts/core-concepts/balance/), not urgent.

### Recommended Improvement

Hoist `_agents_home()` into `utils.py`, beside `find_git_root`, and have both command modules import it — one definition, genuine [high cohesion](https://coupling.dev/posts/core-concepts/balance/) instead of duplication. Collapse `run`/`shell` the same way, into one shared helper parameterised by target name. Both are pure DRY fixes at low distance, with no trade-off.

Leave the Python-vs-Makefile `AGENTS_HOME` duplication as-is. Its low volatility makes the imbalance acceptable, and unifying it would mean either the CLI parsing the Makefile or the Makefile shelling into Python — both add more coupling than they remove. This is the model's pragmatism in action: not every imbalance is worth fixing.

## Issue: Two inconsistent command-registration patterns

**Integration**: `main.py` → `commands/*`
**Severity**: Minor

### Knowledge Leakage

`main.py` mounts `agents` and `pi_agents` as Typer sub-apps via `add_typer(agents.app, …)`, but registers `build`, `network`, and `run` by cherry-picking individual functions: `app.command("build")(build.build)`. Meanwhile `build.py`, `network.py`, and `run.py` each still create a `typer.Typer()` `app` (e.g. `build.py:9`) and decorate their functions with `@app.command()` — yet that `app` object is never mounted anywhere. `main.py` carries an inconsistent [model](https://coupling.dev/posts/dimensions-of-coupling/integration-strength/) of what a "command module" is: sometimes a sub-app, sometimes a bag of functions.

### Complexity Impact

This is a [low cohesion](https://coupling.dev/posts/core-concepts/balance/) signal: the `app` object in `build.py`/`network.py`/`run.py` is dead code that actively misleads. A reader who has seen `agents.app` mounted reasonably assumes `build.app` is mounted too, and must trace `main.py` to discover it is not. The cost is small and contained to one short file, but every new command module forces an unstated choice between two patterns — accidental complexity with no functional purpose.

### Cascading Changes

Low. `main.py` and `commands/*` are at minimal [distance](https://coupling.dev/posts/dimensions-of-coupling/distance/) — one package — and registration changes are infrequent. There is no volatile cascade here; the harm is purely cognitive friction, which is why this is Minor.

### Recommended Improvement

Pick one pattern and apply it everywhere. The simplest: every command module exposes a Typer `app`, and `main.py` only ever calls `add_typer`. If flat top-level commands like `q build` must be preserved (rather than `q build build`), then drop the unused `typer.Typer()` from `build.py`, `network.py`, and `run.py` so their functions are honestly just functions, registered directly. Either way the rule "a command module looks like *X*" becomes true everywhere, and the dead `app` objects disappear. The only cost is a one-time edit; the gain is one fewer decision per future command module.

---

_This analysis was performed using the [Balanced Coupling](https://coupling.dev) model by [Vlad Khononov](https://vladikk.com)._
