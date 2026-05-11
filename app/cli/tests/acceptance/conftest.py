from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tests.acceptance.steps import common_steps  # noqa: F401  (registers shared steps)


@dataclass
class InvocationContext:
    """Shared state for a single Gherkin scenario."""

    runner: CliRunner
    mocks: dict[str, MagicMock]
    git_root: Path
    agents_home: Path
    monkeypatch: pytest.MonkeyPatch
    result: Any = None
    extra: dict[str, Any] = field(default_factory=dict)


@pytest.fixture()
def invocation_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Provide an isolated CLI invocation context with all I/O mocked."""
    repo = tmp_path / "repo"
    repo.mkdir()
    agents_home = tmp_path / ".worktrees"

    monkeypatch.delenv("AGENTS_HOME", raising=False)

    with patch("container_cli.commands.agents.run_make") as m_agents, \
         patch("container_cli.commands.build.run_make") as m_build, \
         patch("container_cli.commands.run.run_make") as m_run, \
         patch("container_cli.commands.network.run_make") as m_network, \
         patch("container_cli.commands.pi_agents.run_make") as m_pi, \
         patch("container_cli.commands.agents.find_git_root", return_value=repo), \
         patch("container_cli.commands.pi_agents.find_git_root", return_value=repo):
        ctx = InvocationContext(
            runner=CliRunner(),
            mocks={
                "agents": m_agents,
                "build": m_build,
                "run": m_run,
                "network": m_network,
                "pi": m_pi,
            },
            git_root=repo,
            agents_home=agents_home,
            monkeypatch=monkeypatch,
        )
        yield ctx
