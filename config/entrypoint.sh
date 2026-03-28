#!/bin/bash
# Entrypoint — copies credentials and supports headless agent mode
#
# Interactive mode (default):
#   entrypoint.sh                          → interactive bash
#   entrypoint.sh <cmd> [args...]          → exec <cmd> [args...]
#
# Headless agent mode:
#   entrypoint.sh --worktree <branch> --task "<prompt>"
#   entrypoint.sh --worktree <branch> --task "<prompt>" --project <name>
#
# Expected volumes:
#   -v <git-root>:/workspace               → main repository (read/write)
#   -v <parent>/.worktrees:/worktrees      → worktrees directory
#   -v ~/.claude:/root/.claudenew:ro       → host credentials
#   -v ~/.claude.json:/root/.claudenew.json:ro

set -euo pipefail

WORKTREE_BRANCH=""
AGENT_TASK=""
PROJECT_NAME=""
PASSTHROUGH_ARGS=()

# ── Parse agent mode flags ────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --worktree) WORKTREE_BRANCH="$2"; shift 2 ;;
        --task)     AGENT_TASK="$2";      shift 2 ;;
        --project)  PROJECT_NAME="$2";    shift 2 ;;
        *)          PASSTHROUGH_ARGS+=("$1"); shift ;;
    esac
done

# ── Copy credentials from host mounts ─────────────────────────────────────────
echo "[entrypoint] Copying credentials..."
cp /root/.claudenew.json /root/.claude.json
mkdir -p /root/.claude
cp -r /root/.claudenew/. /root/.claude/
echo "[entrypoint] Credentials ready."

# ── Agent mode: worktree + headless ───────────────────────────────────────────
if [[ -n "$WORKTREE_BRANCH" ]]; then
    WORKTREE_PATH="/worktrees/${WORKTREE_BRANCH}"

    echo "[entrypoint] Creating worktree: ${WORKTREE_BRANCH} → ${WORKTREE_PATH}"

    # Create destination directory if it doesn't exist
    mkdir -p "$(dirname "$WORKTREE_PATH")"

    # Add worktree (idempotent: if branch already exists, reuses it)
    if git -C /workspace worktree add "$WORKTREE_PATH" -b "$WORKTREE_BRANCH" 2>/dev/null; then
        echo "[entrypoint] Worktree created on new branch: ${WORKTREE_BRANCH}"
    elif git -C /workspace worktree add "$WORKTREE_PATH" "$WORKTREE_BRANCH" 2>/dev/null; then
        echo "[entrypoint] Worktree created on existing branch: ${WORKTREE_BRANCH}"
    else
        echo "[entrypoint] ERROR: could not create worktree for '${WORKTREE_BRANCH}'" >&2
        exit 1
    fi

    cd "$WORKTREE_PATH"
    echo "[entrypoint] Working directory: $(pwd)"

    if [[ -n "$AGENT_TASK" ]]; then
        echo "[entrypoint] Starting Claude agent (headless)..."
        echo "[entrypoint] Task: ${AGENT_TASK}"
        echo "---"
        # Make claude's install path traversable for non-root users (installed under /root/)
        # go+x required: agent is in group root (gid=0), so group bits apply, not others bits
        chmod go+x /root /root/.local /root/.local/share 2>/dev/null || true
        find /root/.local/share/claude -type d -exec chmod go+x {} + 2>/dev/null || true
        find /root/.local/share/claude/versions -maxdepth 1 -type f -exec chmod 755 {} + 2>/dev/null || true
        # Copy credentials to agent user's home (claude requires non-root for --dangerously-skip-permissions)
        cp -r /root/.claude/. /home/agent/.claude/ 2>/dev/null || true
        cp /root/.claude.json /home/agent/.claude.json 2>/dev/null || true
        chown -R agent:agent /home/agent/.claude /home/agent/.claude.json 2>/dev/null || true
        chown -R agent:agent "$WORKTREE_PATH"
        exec su-exec agent env HOME=/home/agent claude --dangerously-skip-permissions -p "$AGENT_TASK"
    else
        # Worktree ready but no task: interactive shell in the worktree
        exec /bin/bash --login
    fi
fi

# ── Interactive mode (original behavior) ──────────────────────────────────────
if [[ ${#PASSTHROUGH_ARGS[@]} -eq 0 ]]; then
    exec /bin/bash --login
else
    exec "${PASSTHROUGH_ARGS[@]}"
fi
