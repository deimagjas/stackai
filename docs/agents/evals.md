# Evals — spawn-agent skill

## What are evals

Evals are automated test cases for the `spawn-agent` skill. They measure whether Claude, with the skill active, produces the correct responses (commands, container names, prompts) for different usage scenarios.

Two configurations are compared:
- **with_skill**: Claude has access to the skill instructions
- **without_skill**: Claude responds without the skill (baseline)

The goal is to quantify the value the skill adds and detect regressions between iterations.

---

## Test scenarios

### Eval 1 — `spawn-feature`

**Test prompt:**
> "I'm working on my stackai project and need you to spawn a virtual agent to implement OAuth2 authentication with JWT tokens in the API. Use branch feat/oauth2."

**Assertions (7):**
1. Generates `container run -d` (detached, not `-it`)
2. Uses `--worktree feat/oauth2` in the command
3. Sanitizes the branch correctly: `feat-oauth2` (one hyphen, not two)
4. Mounts worktrees with `-v $AGENTS_HOME:/worktrees` (not a named volume)
5. Passes `CLAUDE_CODE_OAUTH_TOKEN` as an environment variable
6. The agent prompt is **feature** type (mentions "senior software engineer")
7. Includes a command to follow logs (`container logs -f`)

### Eval 2 — `spawn-test`

**Test prompt:**
> "Spawn an agent to write unit tests for the payment service module. Branch: test/payment-service"

**Assertions (5):**
1. Generates `container run -d` (detached)
2. Uses `--worktree test/payment-service`
3. Prompt is **test** type (mentions QA engineer, coverage, edge cases)
4. Does not use a feature or mutation type prompt
5. Sanitized container name: `test-payment-service` (one hyphen)

### Eval 3 — `list-agents`

**Test prompt:**
> "Show me what agents are currently running. Also list the worktrees that exist."

**Assertions (4):**
1. Runs `container list` (not `docker ps` or `ps aux`)
2. Filters by project prefix (`grep PROJECT_NAME`)
3. Shows worktrees on disk (`ls -la $AGENTS_HOME`)
4. Does not attempt to launch a new agent

### Eval 4 — `monitor-agent`

**Test prompt:**
> "Check what the feat/oauth2 agent is doing right now. Give me a summary of its progress."

**Assertions (4):**
1. Uses `container logs` (not `container run` or `container list`)
2. Correct container name: includes `feat-oauth2` (proper sanitization)
3. Summarizes logs in natural language (no raw dump)
4. Does not launch a new container

---

## File structure

```
~/.claude/skills/spawn-agent/
├── SKILL.md
└── evals/
    ├── evals.json              ← formal definition of the 4 evals
    ├── spawn_feature.md        ← narrative description of the scenario
    ├── spawn_test.md
    ├── list_and_monitor.md
    ├── stop_agent.md
    └── multi_agent.md

~/.claude/skills/spawn-agent-workspace/
├── iteration-1/               ← first iteration of the skill
│   ├── spawn-feature/
│   │   ├── with_skill/outputs/response.md
│   │   ├── with_skill/grading.json
│   │   ├── without_skill/outputs/response.md
│   │   └── without_skill/grading.json
│   ├── spawn-test/
│   ├── list-agents/
│   ├── monitor-agent/
│   └── benchmark.json
└── iteration-2/               ← improved skill (current version)
    ├── spawn-feature/
    ├── spawn-test/
    ├── list-agents/
    ├── monitor-agent/
    └── benchmark.json
```

---

## Results

### Iteration 1 — initial skill

| Eval | with_skill | without_skill | Bug found |
|---|---|---|---|
| spawn-feature | 85.7% | 0% | `feat--oauth2` double hyphen |
| spawn-test | 80% | 20% | `test--payment-service` double hyphen |
| list-agents | 25% | 50%* | Bash blocked in eval |
| monitor-agent | 50% | 50%* | Bash blocked in eval |
| **Average** | **60.7%** | **30%** | |

*The eval environment blocked Bash — the list/monitor evals reflect skill knowledge, not actual execution.

**Critical bug identified:** `tr '/_ ' '---'` was ambiguous — agents interpreted `'---'` as "triple hyphen" producing `feat--oauth2`. It should be `tr '/_ ' '-'`.

### Iteration 2 — corrected skill (current)

| Eval | with_skill | without_skill | Delta |
|---|---|---|---|
| spawn-feature | **100%** | 0% | **+100%** |
| spawn-test | **100%** | 20% | **+80%** |
| list-agents | **100%** | 50% | **+50%** |
| monitor-agent | **100%** | 50% | **+50%** |
| **Average** | **100%** | **30%** | **+70%** |

**Changes that achieved 100%:**
1. `tr '/_ ' '-'` — unambiguous replacement, always one hyphen
2. `AGENTS_HOME` — environment variable replaces hardcoded paths
3. `PROJECT_NAME=$(basename "$GIT_ROOT")` — dynamic project name
4. `container network list --format json` — reliable network parsing
5. Apple Container CLI docs included in the skill

---

## How to run evals

### Prerequisites

```bash
# Install the skill-creator plugin
/plugin skill-creator   # from Claude Code
/reload-plugins
```

### Run evals with skill-creator

```
/skill-creator:skill-creator run evals for the spawn-agent skill at ~/.claude/skills/spawn-agent/
```

The process:
1. Reads `evals/evals.json`
2. Launches runs in parallel (with_skill + without_skill)
3. Generates `benchmark.json` and opens the HTML viewer
4. You review outputs and leave feedback
5. The skill is improved and the cycle repeats

### Run directly

```bash
SKILL_CREATOR=~/.claude/plugins/cache/claude-plugins-official/skill-creator/d5c15b861cd2/skills/skill-creator

# Generate static viewer
python3.13 "$SKILL_CREATOR/eval-viewer/generate_review.py" \
  ~/.claude/skills/spawn-agent-workspace/iteration-2 \
  --skill-name "spawn-agent" \
  --benchmark ~/.claude/skills/spawn-agent-workspace/iteration-2/benchmark.json \
  --static /tmp/spawn-agent-review.html

open /tmp/spawn-agent-review.html
```

> **Python required:** Python 3.10+ (the system may have 3.9). Use `~/.local/share/uv/python/cpython-3.13.0-macos-aarch64-none/bin/python3.13`

---

## How to add new evals

### 1. Add to `evals.json`

```json
{
  "id": 5,
  "prompt": "Stop the feat/oauth2 agent and clean up its worktree",
  "expected_output": "Claude runs container stop stackai-feat-oauth2 and optionally removes the worktree",
  "files": [],
  "expectations": [
    "Runs container stop with correct container name stackai-feat-oauth2",
    "Does NOT attempt to spawn a new container",
    "If user asked for cleanup: runs git worktree remove and rm -rf"
  ]
}
```

### 2. Create a description file (optional)

```
~/.claude/skills/spawn-agent/evals/stop_agent.md
```

### 3. Run the new iteration

```
/skill-creator:skill-creator run evals for spawn-agent, iterate from iteration-2
```

---

## Interpreting benchmark.json

```json
{
  "run_summary": {
    "with_skill":    { "pass_rate": {"mean": 1.0, "stddev": 0.0} },
    "without_skill": { "pass_rate": {"mean": 0.3, "stddev": 0.2} },
    "delta":         { "pass_rate": "+0.70" }
  }
}
```

- **pass_rate mean > 0.8** with skill → skill is working well
- **delta > 0.5** → skill adds significant value
- **high stddev** → eval is possibly flaky or environment-dependent
- **with_skill ≈ without_skill** → assertion is not discriminating (review it)

---

## Running Evals: Local Only

Evals for the `spawn-agent` skill **cannot run in CI/CD pipelines**. They must be executed locally on a developer machine due to the following hard requirements:

### Requirements

1. **Claude Code CLI in headless mode** — Evals are driven by Claude Code, which must be installed and available as `claude` in your PATH. The eval runner invokes it in headless (non-interactive) mode to capture responses programmatically.

2. **Apple Container CLI (macOS 26+)** — The spawn-agent skill generates `container run`, `container list`, and `container logs` commands targeting Apple's native container runtime. This CLI is only available on macOS 26 (Tahoe) or later. Linux and older macOS versions are not supported.

3. **A valid `CLAUDE_CONTAINER_OAUTH_TOKEN`** — The containerized agent authenticates via an OAuth token passed as an environment variable. Without a valid token, spawned containers cannot execute Claude Code inside the container. This token cannot be safely stored in CI secrets due to rotation and scope constraints.

4. **Mounted git worktrees** — The skill mounts the host's `$AGENTS_HOME` directory (typically `~/agents`) into containers at `/worktrees`. The eval environment must have a real git repository with worktree support. CI runners typically lack the necessary filesystem layout.

### Step-by-step local execution

```bash
# 1. Verify prerequisites
claude --version                    # Claude Code CLI is installed
container --version                 # Apple Container CLI is available (macOS 26+)
echo $CLAUDE_CONTAINER_OAUTH_TOKEN  # Token is set and non-empty

# 2. Ensure the skill is installed
ls ~/.claude/skills/spawn-agent/SKILL.md

# 3. Ensure the eval definitions exist
ls ~/.claude/skills/spawn-agent/evals/evals.json

# 4. Set up the agents home directory if it doesn't exist
export AGENTS_HOME="${AGENTS_HOME:-$HOME/agents}"
mkdir -p "$AGENTS_HOME"

# 5. Run evals via skill-creator (recommended)
# Open Claude Code and run:
/plugin skill-creator
/reload-plugins
/skill-creator:skill-creator run evals for the spawn-agent skill at ~/.claude/skills/spawn-agent/

# 6. Or run the static viewer directly
SKILL_CREATOR=~/.claude/plugins/cache/claude-plugins-official/skill-creator/d5c15b861cd2/skills/skill-creator

python3.13 "$SKILL_CREATOR/eval-viewer/generate_review.py" \
  ~/.claude/skills/spawn-agent-workspace/iteration-2 \
  --skill-name "spawn-agent" \
  --benchmark ~/.claude/skills/spawn-agent-workspace/iteration-2/benchmark.json \
  --static /tmp/spawn-agent-review.html

open /tmp/spawn-agent-review.html
```

> **Note:** If evals appear to hang or produce empty results, verify that your `CLAUDE_CONTAINER_OAUTH_TOKEN` has not expired and that the Apple Container daemon is running (`container system info`).
