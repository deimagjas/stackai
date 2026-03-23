from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def fake_git_root(tmp_path: Path):
    """Patch find_git_root to return a temp directory."""
    with patch("container_cli.utils.find_git_root", return_value=tmp_path):
        yield tmp_path


@pytest.fixture()
def mock_run_make():
    """Patch run_make across all command modules."""
    with patch("container_cli.commands.agents.run_make") as m_agents, \
         patch("container_cli.commands.build.run_make") as m_build, \
         patch("container_cli.commands.run.run_make") as m_run, \
         patch("container_cli.commands.network.run_make") as m_network:
        yield {
            "agents": m_agents,
            "build": m_build,
            "run": m_run,
            "network": m_network,
        }


@pytest.fixture()
def mock_check_token():
    """Patch check_token across command modules that use it."""
    with patch("container_cli.commands.agents.check_token") as m_agents, \
         patch("container_cli.commands.run.check_token") as m_run:
        yield {"agents": m_agents, "run": m_run}


@pytest.fixture()
def env_with_token(monkeypatch: pytest.MonkeyPatch):
    """Set the CLAUDE_CONTAINER_OAUTH_TOKEN env var."""
    monkeypatch.setenv("CLAUDE_CONTAINER_OAUTH_TOKEN", "test-token-123")
