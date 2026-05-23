"""End-to-end test: orchestrator <-> Claude agent communication.

Spawns a real Claude agent container through the ``q`` CLI, waits for it to
finish, and asserts the orchestrator receives the agent's report through every
channel: ``status.json``, the persisted log, the ``[agent:status]`` markers,
and the git commit on the worktree branch.

Opt-in and local-only — see ``tests/e2e/conftest.py``.
"""

from __future__ import annotations

import json

import pytest

_TASK = (
    "Create a file named E2E_OK.txt in the current directory containing "
    "exactly the text PASS, then stage and commit it with git."
)


@pytest.mark.e2e
def test_claude_agent_round_trip(
    require_container_cli,
    require_claude_token,
    require_claude_image,
    isolated_agents_home,
    unique_branch,
    run_q,
    wait_for_terminal_phase,
    agent_cleanup,
):
    """A spawned Claude agent does the task and reports back to the orchestrator."""
    branch = unique_branch

    # Outbound — the orchestrator ensures the network exists, then dispatches.
    network = run_q("network")
    assert network.returncode == 0, network.stderr

    spawn = run_q("spawn", "--branch", branch, "--task", _TASK)
    agent_cleanup(branch, "claude")
    assert spawn.returncode == 0, f"spawn failed:\n{spawn.stdout}\n{spawn.stderr}"

    # Inbound channel 1 — status.json reaches a terminal phase.
    status = wait_for_terminal_phase(isolated_agents_home, branch)
    assert status["phase"] == "completed", f"agent did not complete: {status}"
    assert status["exit_code"] == 0, f"agent exited non-zero: {status}"
    assert status["commits"] >= 1, f"agent reported no commit: {status}"

    # Outbound result — the task produced real work in the shared worktree.
    artifact = isolated_agents_home / branch / "E2E_OK.txt"
    assert artifact.is_file(), f"agent did not create {artifact}"
    assert artifact.read_text().strip() == "PASS"

    # Inbound channel 2 — `q agents status` surfaces the report to the orchestrator.
    cli_status = run_q("agents", "status", "--branch", branch)
    assert cli_status.returncode == 0, cli_status.stderr
    assert json.loads(cli_status.stdout)["phase"] == "completed"

    # Inbound channel 3 — the persisted log and the [agent:status] markers.
    logs = run_q("agents", "logs", "--branch", branch)
    assert logs.returncode == 0, logs.stderr
    assert logs.stdout.strip(), "agent log is empty"

    summary = run_q("agents", "summary", "--branch", branch)
    assert summary.returncode == 0, summary.stderr
    assert "PHASE=completed" in summary.stdout, summary.stdout
