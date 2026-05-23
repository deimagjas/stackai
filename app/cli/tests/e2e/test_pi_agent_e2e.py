"""End-to-end test: orchestrator <-> PI agent communication.

Spawns a real PI agent container (local ``mlx_lm.server`` backend) through the
``q pi`` CLI and asserts the orchestrator receives the agent's report. PI
agents need no Claude token — they authenticate against the local model — but
they do need the model server running on the host.

This test validates the *communication* round-trip, not model quality: a
terminal ``status.json`` carrying ``agent_kind="pi"`` plus a captured log proves
the task was delivered and the report came back.

``MAX_PI_AGENTS`` enforcement is intentionally not E2E-tested here — it would
require a racy spawn-while-running attempt; it is covered by the Makefile logic
and the mocked acceptance suite.

Opt-in and local-only — see ``tests/e2e/conftest.py``.
"""

from __future__ import annotations

import json

import pytest

_TASK = (
    "Create a file named E2E_PI_OK.txt in the current directory containing exactly the text PASS."
)


@pytest.mark.e2e
def test_pi_agent_round_trip(
    require_container_cli,
    require_pi_image,
    require_mlx_server,
    isolated_agents_home,
    unique_branch,
    run_q,
    wait_for_terminal_phase,
    agent_cleanup,
):
    """A spawned PI agent runs against the local model and reports back."""
    branch = unique_branch

    # Outbound — dispatch the task to a PI container (no Claude token needed).
    network = run_q("network")
    assert network.returncode == 0, network.stderr

    spawn = run_q("pi", "spawn", "--branch", branch, "--task", _TASK)
    agent_cleanup(branch, "pi")
    assert spawn.returncode == 0, f"pi spawn failed:\n{spawn.stdout}\n{spawn.stderr}"

    # Inbound channel 1 — status.json reaches a terminal phase, tagged as PI.
    status = wait_for_terminal_phase(isolated_agents_home, branch)
    assert status["phase"] == "completed", f"PI agent did not complete: {status}"
    assert status["agent_kind"] == "pi", f"status not tagged as PI: {status}"

    # Inbound channel 2 — `q pi status` surfaces the PI report to the orchestrator.
    cli_status = run_q("pi", "status", "--branch", branch)
    assert cli_status.returncode == 0, cli_status.stderr
    assert json.loads(cli_status.stdout)["agent_kind"] == "pi"

    # Inbound channel 3 — `q pi list` filters this worktree in by agent_kind=pi.
    pi_list = run_q("pi", "list")
    assert pi_list.returncode == 0, pi_list.stderr
    assert branch in pi_list.stdout, f"branch {branch} not listed by `q pi list`"

    # Inbound channel 4 — the persisted log is captured.
    logs = run_q("pi", "logs", "--branch", branch)
    assert logs.returncode == 0, logs.stderr
    assert logs.stdout.strip(), "PI agent log is empty"
