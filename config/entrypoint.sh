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

# ── Functions ─────────────────────────────────────────────────────────────────

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --worktree) WORKTREE_BRANCH="$2"; shift 2 ;;
            --task)     AGENT_TASK="$2";      shift 2 ;;
            --project)  PROJECT_NAME="$2";    shift 2 ;;
            *)          PASSTHROUGH_ARGS+=("$1"); shift ;;
        esac
    done
}

copy_credentials() {
    echo "[entrypoint] Copying credentials..."
    cp /root/.claudenew.json /root/.claude.json
    mkdir -p /root/.claude
    cp -r /root/.claudenew/. /root/.claude/
    echo "[entrypoint] Credentials ready."
}

create_worktree() {
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
}

setup_agent_perms() {
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
}

write_status() {
    local phase="$1"; shift
    local now
    now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    ( printf '{"phase":"%s","branch":"%s","task":"%s","started_at":"%s"}\n' \
        "$phase" "$WORKTREE_BRANCH" "$AGENT_TASK" "${AGENT_STARTED_AT:-${now}}" \
        > "${AGENT_DIR}/status.json" ) 2>/dev/null || true
}

emit_marker() {
    local phase="$1"; shift
    echo "[agent:status] PHASE=${phase} BRANCH=${WORKTREE_BRANCH} $*"
}

run_agent() {
    AGENT_DIR="${WORKTREE_PATH}/.agent"
    mkdir -p "$AGENT_DIR"
    chown -R agent:agent "$AGENT_DIR"

    # Add .agent/ to worktree .gitignore (safe if dir doesn't exist yet)
    if ! grep -qxF '.agent/' "${WORKTREE_PATH}/.gitignore" 2>/dev/null; then
        echo '.agent/' >> "${WORKTREE_PATH}/.gitignore" 2>/dev/null || true
    fi

    AGENT_STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local start_epoch
    start_epoch=$(date +%s)

    write_status "starting"
    emit_marker "starting"

    write_status "working"
    emit_marker "working"

    # Run claude with tee to persist logs; capture exit code through pipe
    set +e
    su-exec agent env HOME=/home/agent claude --dangerously-skip-permissions \
        -p "$AGENT_TASK" 2>&1 | tee "$AGENT_DIR/agent.log"
    local exit_code=${PIPESTATUS[0]}
    set -e

    # Collect post-run metrics
    local commit_count last_commit finished_at end_epoch duration_secs
    commit_count=$(git -C "$WORKTREE_PATH" rev-list --count HEAD 2>/dev/null || echo 0)
    last_commit=$(git -C "$WORKTREE_PATH" log --oneline -1 2>/dev/null || echo "none")
    finished_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    end_epoch=$(date +%s)
    duration_secs=$((end_epoch - start_epoch))

    local final_phase="completed"
    [ "$exit_code" -ne 0 ] && final_phase="errored"

    # Write final status.json
    ( printf '{
  "phase": "%s",
  "branch": "%s",
  "task": "%s",
  "started_at": "%s",
  "finished_at": "%s",
  "duration_secs": %d,
  "exit_code": %d,
  "commits": %s,
  "last_commit": "%s"
}\n' "$final_phase" "$WORKTREE_BRANCH" "$AGENT_TASK" \
     "$AGENT_STARTED_AT" "$finished_at" "$duration_secs" \
     "$exit_code" "$commit_count" "$last_commit" \
     > "$AGENT_DIR/status.json" ) 2>/dev/null || true

    emit_marker "$final_phase" "EXIT_CODE=${exit_code}" "COMMITS=${commit_count}" "DURATION=${duration_secs}s"

    exit "$exit_code"
}

run_interactive() {
    if [[ ${#PASSTHROUGH_ARGS[@]} -eq 0 ]]; then
        exec /bin/bash --login
    else
        exec "${PASSTHROUGH_ARGS[@]}"
    fi
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
    parse_args "$@"
    copy_credentials

    if [[ -n "$WORKTREE_BRANCH" ]]; then
        create_worktree
        if [[ -n "$AGENT_TASK" ]]; then
            setup_agent_perms
            run_agent
        else
            run_interactive
        fi
    else
        run_interactive
    fi
}

main "$@"
