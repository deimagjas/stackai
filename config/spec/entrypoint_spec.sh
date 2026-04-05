# shellcheck shell=bash
Describe "entrypoint.sh"

  # ── Helper: run the entrypoint with all external commands mocked ───────────
  # Creates a wrapper script that overrides dangerous commands with stubs
  # that print tagged lines to stdout for assertion. The tags are:
  #   [MOCK] — cp, mkdir, chmod, find, chown, su-exec, claude, git
  #   [EXEC] — exec calls
  #   [CD]   — cd calls

  setup_entrypoint() {
    export ENTRYPOINT_SH="$SHELLSPEC_PROJECT_ROOT/entrypoint.sh"
    # Default: git worktree add succeeds on first try (new branch)
    export GIT_WORKTREE_NEW_BRANCH_SUCCEEDS="true"
    export GIT_WORKTREE_EXISTING_BRANCH_SUCCEEDS="true"
  }

  # Run the entrypoint with mocked externals
  run_entrypoint() {
    local wrapper="${SHELLSPEC_TMPDIR}/wrapper_$$.sh"
    cat > "$wrapper" <<'WRAPPER_EOF'
#!/bin/bash

cp() { echo "[MOCK] cp $*"; }
mkdir() { echo "[MOCK] mkdir $*"; }
chmod() { echo "[MOCK] chmod $*"; }
find() { echo "[MOCK] find $*"; }
chown() { echo "[MOCK] chown $*"; }
dirname() { command dirname "$@"; }
pwd() { echo "/mocked/pwd"; }
date() {
  if [[ "$*" == *"+%s"* ]]; then
    echo "1000000"
  else
    echo "2026-01-01T00:00:00Z"
  fi
}
tee() { command cat; }
grep() {
  # For .gitignore check, pretend .agent/ is already there
  if [[ "$*" == *".gitignore"* ]]; then
    return 0
  fi
  command grep "$@"
}
cat() {
  # Intercept heredoc writes to status.json (cat > file)
  if [[ "${1:-}" == ">" ]]; then
    echo "[MOCK] cat > $2"
    command cat > /dev/null
    return 0
  fi
  command cat "$@"
}

su-exec() { echo "[MOCK] su-exec $*"; }

git() {
  echo "[MOCK] git $*"
  if [[ "$*" == *"worktree add"*"-b"* ]]; then
    [[ "$GIT_WORKTREE_NEW_BRANCH_SUCCEEDS" == "true" ]] && return 0 || return 1
  elif [[ "$*" == *"worktree add"* ]]; then
    [[ "$GIT_WORKTREE_EXISTING_BRANCH_SUCCEEDS" == "true" ]] && return 0 || return 1
  elif [[ "$*" == *"rev-list --count"* ]]; then
    echo "3"
    return 0
  elif [[ "$*" == *"log --oneline -1"* ]]; then
    echo "abc1234 test commit"
    return 0
  fi
  return 0
}

cd() {
  echo "[CD] cd $*"
  return 0
}

exec() {
  echo "[EXEC] exec $*"
  exit 0
}

export -f cp mkdir chmod find chown git cd exec pwd dirname su-exec date tee grep cat

source "$ENTRYPOINT_SH" "$@"
WRAPPER_EOF
    chmod +x "$wrapper"

    env \
      GIT_WORKTREE_NEW_BRANCH_SUCCEEDS="$GIT_WORKTREE_NEW_BRANCH_SUCCEEDS" \
      GIT_WORKTREE_EXISTING_BRANCH_SUCCEEDS="$GIT_WORKTREE_EXISTING_BRANCH_SUCCEEDS" \
      ENTRYPOINT_SH="$ENTRYPOINT_SH" \
      bash "$wrapper" "$@"
    return $?
  }

  BeforeEach 'setup_entrypoint'

  # ═══════════════════════════════════════════════════════════════════════════
  # 1. ARGUMENT PARSING
  # ═══════════════════════════════════════════════════════════════════════════
  Describe "Argument Parsing"
    It "sets WORKTREE_BRANCH with --worktree flag"
      When run run_entrypoint --worktree my-branch
      The output should include "Creating worktree: my-branch"
      The status should equal 0
    End

    It "sets AGENT_TASK with --task flag"
      When run run_entrypoint --worktree test-branch --task "fix the bug"
      The output should include "Task: fix the bug"
      The status should equal 0
    End

    It "sets PROJECT_NAME with --project flag"
      When run run_entrypoint --worktree test-branch --task "do stuff" --project my-project
      The output should include "Task: do stuff"
      The status should equal 0
    End

    It "collects unknown args into PASSTHROUGH_ARGS"
      When run run_entrypoint /usr/bin/python3 script.py
      The output should include "[EXEC] exec /usr/bin/python3 script.py"
      The status should equal 0
    End

    It "preserves multiple passthrough args"
      When run run_entrypoint ls -la /tmp
      The output should include "[EXEC] exec ls -la /tmp"
      The status should equal 0
    End

    It "handles all three flags together"
      When run run_entrypoint --worktree feat/xyz --task "implement feature" --project acme
      The output should include "Creating worktree: feat/xyz"
      The output should include "Task: implement feature"
      The status should equal 0
    End

    It "handles empty string values for --worktree"
      When run run_entrypoint --worktree ""
      The output should not include "Creating worktree"
      The output should include "[EXEC] exec /bin/bash --login"
      The status should equal 0
    End

    It "handles mixed flags and passthrough args"
      When run run_entrypoint --worktree my-branch --task "hello" extra-arg
      The output should include "Creating worktree: my-branch"
      The status should equal 0
    End
  End

  # ═══════════════════════════════════════════════════════════════════════════
  # 2. CREDENTIAL COPYING
  # ═══════════════════════════════════════════════════════════════════════════
  Describe "Credential Copying"
    It "copies .claudenew.json to .claude.json"
      When run run_entrypoint
      The output should include "[MOCK] cp /root/.claudenew.json /root/.claude.json"
      The status should equal 0
    End

    It "creates /root/.claude directory"
      When run run_entrypoint
      The output should include "[MOCK] mkdir -p /root/.claude"
      The status should equal 0
    End

    It "copies .claudenew directory contents recursively"
      When run run_entrypoint
      The output should include "[MOCK] cp -r /root/.claudenew/. /root/.claude/"
      The status should equal 0
    End

    It "prints start message"
      When run run_entrypoint
      The output should include "[entrypoint] Copying credentials..."
      The status should equal 0
    End

    It "prints completion message"
      When run run_entrypoint
      The output should include "[entrypoint] Credentials ready."
      The status should equal 0
    End
  End

  # ═══════════════════════════════════════════════════════════════════════════
  # 3. INTERACTIVE MODE
  # ═══════════════════════════════════════════════════════════════════════════
  Describe "Interactive Mode"
    It "execs bash --login when no args given"
      When run run_entrypoint
      The output should include "[EXEC] exec /bin/bash --login"
      The status should equal 0
    End

    It "execs a single passthrough command"
      When run run_entrypoint /usr/bin/python3
      The output should include "[EXEC] exec /usr/bin/python3"
      The status should equal 0
    End

    It "execs multiple passthrough args as a command"
      When run run_entrypoint ls -la /workspace
      The output should include "[EXEC] exec ls -la /workspace"
      The status should equal 0
    End

    It "does not trigger worktree mode without --worktree"
      When run run_entrypoint some-command
      The output should not include "Creating worktree"
      The output should include "[EXEC] exec some-command"
      The status should equal 0
    End

    It "does not invoke su-exec in interactive mode"
      When run run_entrypoint
      The output should not include "su-exec"
      The status should equal 0
    End

    It "does not invoke claude in interactive mode"
      When run run_entrypoint
      The output should not include "claude --dangerously"
      The status should equal 0
    End
  End

  # ═══════════════════════════════════════════════════════════════════════════
  # 4. WORKTREE CREATION
  # ═══════════════════════════════════════════════════════════════════════════
  Describe "Worktree Creation"
    It "creates worktree on new branch via git worktree add -b"
      When run run_entrypoint --worktree feat/new-feature
      The output should include "[MOCK] git -C /workspace worktree add /worktrees/feat/new-feature -b feat/new-feature"
      The output should include "Worktree created on new branch: feat/new-feature"
      The status should equal 0
    End

    It "falls back to existing branch when new branch fails"
      export GIT_WORKTREE_NEW_BRANCH_SUCCEEDS="false"
      When run run_entrypoint --worktree feat/existing
      The output should include "[MOCK] git -C /workspace worktree add /worktrees/feat/existing feat/existing"
      The output should include "Worktree created on existing branch: feat/existing"
      The status should equal 0
    End

    It "exits with ERROR when both worktree attempts fail"
      export GIT_WORKTREE_NEW_BRANCH_SUCCEEDS="false"
      export GIT_WORKTREE_EXISTING_BRANCH_SUCCEEDS="false"
      When run run_entrypoint --worktree feat/broken
      The output should include "Creating worktree: feat/broken"
      The stderr should include "ERROR"
      The stderr should include "feat/broken"
      The status should equal 1
    End

    It "creates parent directory with mkdir -p"
      When run run_entrypoint --worktree feat/deep/nested
      The output should include "[MOCK] mkdir -p /worktrees/feat/deep"
      The status should equal 0
    End

    It "computes WORKTREE_PATH as /worktrees/<branch>"
      When run run_entrypoint --worktree my-branch
      The output should include "/worktrees/my-branch"
      The status should equal 0
    End

    It "changes directory to the worktree path"
      When run run_entrypoint --worktree test-branch
      The output should include "[CD] cd /worktrees/test-branch"
      The status should equal 0
    End

    It "handles nested branch names with slashes"
      When run run_entrypoint --worktree feature/team/ticket-123
      The output should include "Creating worktree: feature/team/ticket-123"
      The output should include "/worktrees/feature/team/ticket-123"
      The status should equal 0
    End

    It "creates parent dirs for deeply nested branch"
      When run run_entrypoint --worktree a/b/c/d
      The output should include "[MOCK] mkdir -p /worktrees/a/b/c"
      The status should equal 0
    End

    It "prints working directory after cd"
      When run run_entrypoint --worktree my-branch
      The output should include "[entrypoint] Working directory:"
      The status should equal 0
    End
  End

  # ═══════════════════════════════════════════════════════════════════════════
  # 5. AGENT MODE WITH TASK
  # ═══════════════════════════════════════════════════════════════════════════
  Describe "Agent Mode with Task"
    It "runs chmod go+x on /root paths"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[MOCK] chmod go+x /root /root/.local /root/.local/share"
      The status should equal 0
    End

    It "runs find on claude directories for traversability"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[MOCK] find /root/.local/share/claude -type d -exec chmod go+x"
      The status should equal 0
    End

    It "runs find for claude version binaries"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[MOCK] find /root/.local/share/claude/versions -maxdepth 1 -type f -exec chmod 755"
      The status should equal 0
    End

    It "copies credentials to /home/agent"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[MOCK] cp -r /root/.claude/. /home/agent/.claude/"
      The output should include "[MOCK] cp /root/.claude.json /home/agent/.claude.json"
      The status should equal 0
    End

    It "chowns agent home credentials"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[MOCK] chown -R agent:agent /home/agent/.claude /home/agent/.claude.json"
      The status should equal 0
    End

    It "chowns worktree directory to agent"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[MOCK] chown -R agent:agent /worktrees/agent-br"
      The status should equal 0
    End

    It "runs su-exec with correct claude command"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[MOCK] su-exec agent env HOME=/home/agent claude --dangerously-skip-permissions -p do work"
      The status should equal 0
    End

    It "prints agent initialization messages"
      When run run_entrypoint --worktree agent-br --task "implement feature"
      The output should include "[entrypoint] Starting Claude agent (headless)..."
      The output should include "[entrypoint] Task: implement feature"
      The output should include "---"
      The status should equal 0
    End

    It "tolerates chmod failures via || true"
      When run run_entrypoint --worktree agent-br --task "work"
      The status should equal 0
      The output should include "[MOCK] su-exec"
    End

    It "passes task with special characters"
      When run run_entrypoint --worktree agent-br --task "fix bug #123 & deploy"
      The output should include "Task: fix bug #123 & deploy"
      The status should equal 0
    End
  End

  # ═══════════════════════════════════════════════════════════════════════════
  # 6. WORKTREE WITHOUT TASK
  # ═══════════════════════════════════════════════════════════════════════════
  Describe "Worktree Without Task"
    It "execs bash --login when worktree set but no task"
      When run run_entrypoint --worktree my-branch
      The output should include "[EXEC] exec /bin/bash --login"
      The status should equal 0
    End

    It "does not invoke su-exec without task"
      When run run_entrypoint --worktree my-branch
      The output should not include "[MOCK] chown"
      The output should not include "[MOCK] su-exec"
      The status should equal 0
    End

    It "does not invoke claude without task"
      When run run_entrypoint --worktree my-branch
      The output should not include "claude --dangerously"
      The status should equal 0
    End

    It "changes to worktree directory before interactive shell"
      When run run_entrypoint --worktree my-branch
      The output should include "[CD] cd /worktrees/my-branch"
      The output should include "[EXEC] exec /bin/bash --login"
      The status should equal 0
    End
  End

  # ═══════════════════════════════════════════════════════════════════════════
  # 7. EDGE CASES
  # ═══════════════════════════════════════════════════════════════════════════
  Describe "Edge Cases"
    It "has set -euo pipefail active"
      Data < <(head -20 "$SHELLSPEC_PROJECT_ROOT/entrypoint.sh")
      When run cat
      The output should include "set -euo pipefail"
      The status should equal 0
    End

    It "treats empty WORKTREE_BRANCH as unset (interactive mode)"
      When run run_entrypoint --worktree ""
      The output should not include "Creating worktree"
      The output should include "[EXEC] exec /bin/bash --login"
      The status should equal 0
    End

    It "handles task with double quotes"
      When run run_entrypoint --worktree br --task 'say "hello world"'
      The output should include 'Task: say "hello world"'
      The status should equal 0
    End

    It "handles task with newline-like content"
      When run run_entrypoint --worktree br --task "line1 line2"
      The output should include "Task: line1 line2"
      The status should equal 0
    End

    It "handles branch name with dots"
      When run run_entrypoint --worktree release/v1.2.3
      The output should include "Creating worktree: release/v1.2.3"
      The status should equal 0
    End

    It "handles branch name with hyphens and underscores"
      When run run_entrypoint --worktree fix/my_feature-branch
      The output should include "Creating worktree: fix/my_feature-branch"
      The status should equal 0
    End

    It "credential copy runs before worktree mode"
      When run run_entrypoint --worktree my-branch --task "work"
      The output should include "Copying credentials"
      The output should include "Credentials ready"
      The output should include "Creating worktree"
      The status should equal 0
    End
  End

  # ═══════════════════════════════════════════════════════════════════════════
  # 8. AGENT MONITORING
  # ═══════════════════════════════════════════════════════════════════════════
  Describe "Agent Monitoring"
    It "emits starting lifecycle marker"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[agent:status] PHASE=starting BRANCH=agent-br"
      The status should equal 0
    End

    It "emits working lifecycle marker"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[agent:status] PHASE=working BRANCH=agent-br"
      The status should equal 0
    End

    It "emits completed lifecycle marker on success"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[agent:status] PHASE=completed BRANCH=agent-br"
      The output should include "EXIT_CODE=0"
      The output should include "COMMITS="
      The output should include "DURATION="
      The status should equal 0
    End

    It "creates .agent directory in worktree"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[MOCK] mkdir -p /worktrees/agent-br/.agent"
      The status should equal 0
    End

    It "runs su-exec without exec (allows post-processing)"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[MOCK] su-exec agent env HOME=/home/agent claude"
      The output should not include "[EXEC] exec su-exec"
      The status should equal 0
    End

    It "collects commit count after agent finishes"
      When run run_entrypoint --worktree agent-br --task "do work"
      The output should include "[MOCK] git -C /worktrees/agent-br rev-list --count HEAD"
      The status should equal 0
    End
  End

End
