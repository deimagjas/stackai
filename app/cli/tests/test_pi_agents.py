"""Unit tests for the pi_agents command module.

Mirrors test_agents.py at the unit level. PI agents do NOT use
CLAUDE_CONTAINER_OAUTH_TOKEN — they hit the local mlx_lm.server.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from container_cli.commands.pi_agents import (
    _agents_home,
    build,
    follow,
    list_agents,
    logs,
    spawn,
    status,
    stop,
)


class TestSpawn:
    def test_basic_spawn(self, mock_run_make):
        spawn(branch="pi/a", task="rename", cpus=None, memory=None, image=None, base_url=None, model_id=None)
        mock_run_make["pi"].assert_called_once_with(
            "spawn-pi", {"BRANCH": "pi/a", "TASK": "rename"}
        )

    def test_spawn_with_cpus(self, mock_run_make):
        spawn(branch="b", task="t", cpus=4, memory=None, image=None, base_url=None, model_id=None)
        call_vars = mock_run_make["pi"].call_args[0][1]
        assert call_vars["CPUS"] == "4"

    def test_spawn_with_memory(self, mock_run_make):
        spawn(branch="b", task="t", cpus=None, memory="8G", image=None, base_url=None, model_id=None)
        call_vars = mock_run_make["pi"].call_args[0][1]
        assert call_vars["MEMORY"] == "8G"

    def test_spawn_with_image(self, mock_run_make):
        spawn(branch="b", task="t", cpus=None, memory=None, image="claude-pi:custom", base_url=None, model_id=None)
        call_vars = mock_run_make["pi"].call_args[0][1]
        assert call_vars["PI_IMAGE"] == "claude-pi:custom"

    def test_spawn_with_base_url(self, mock_run_make):
        spawn(branch="b", task="t", cpus=None, memory=None, image=None, base_url="http://10.0.0.5:9000/v1", model_id=None)
        call_vars = mock_run_make["pi"].call_args[0][1]
        assert call_vars["PI_BASE_URL"] == "http://10.0.0.5:9000/v1"

    def test_spawn_with_model_id(self, mock_run_make):
        spawn(branch="b", task="t", cpus=None, memory=None, image=None, base_url=None, model_id="mlx-community/gemma-4-26b-a4b-it-4bit")
        call_vars = mock_run_make["pi"].call_args[0][1]
        assert call_vars["PI_MODEL_ID"] == "mlx-community/gemma-4-26b-a4b-it-4bit"

    def test_spawn_does_not_require_token(self, mock_run_make, monkeypatch):
        monkeypatch.delenv("CLAUDE_CONTAINER_OAUTH_TOKEN", raising=False)
        spawn(branch="b", task="t", cpus=None, memory=None, image=None, base_url=None, model_id=None)
        mock_run_make["pi"].assert_called_once()


class TestBuild:
    def test_basic_build(self, mock_run_make):
        build(image=None, dockerfile=None)
        mock_run_make["pi"].assert_called_once_with("build-pi", {})

    def test_build_with_overrides(self, mock_run_make):
        build(image="claude-pi:custom", dockerfile="Dockerfile.pi.custom")
        mock_run_make["pi"].assert_called_once_with(
            "build-pi",
            {"PI_IMAGE": "claude-pi:custom", "PI_DOCKERFILE": "Dockerfile.pi.custom"},
        )


class TestListAgents:
    def test_calls_run_make(self, mock_run_make):
        list_agents()
        mock_run_make["pi"].assert_called_once_with("list-pi-agents")


class TestLogs:
    def test_passes_branch(self, mock_run_make):
        logs(branch="pi/x")
        mock_run_make["pi"].assert_called_once_with(
            "logs-pi-agent", {"BRANCH": "pi/x"}
        )


class TestFollow:
    def test_passes_branch_with_tty(self, mock_run_make):
        follow(branch="pi/x")
        mock_run_make["pi"].assert_called_once_with(
            "follow-pi-agent", {"BRANCH": "pi/x"}, tty=True
        )


class TestStop:
    def test_passes_branch(self, mock_run_make):
        stop(branch="pi/x")
        mock_run_make["pi"].assert_called_once_with(
            "stop-pi-agent", {"BRANCH": "pi/x"}
        )


class TestStatus:
    def test_missing_status_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path))
        with pytest.raises(typer.Exit) as exc_info:
            status(branch="pi/x")
        assert exc_info.value.exit_code == 1

    def test_reads_status_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path))
        status_file = tmp_path / "pi/x" / ".agent" / "status.json"
        status_file.parent.mkdir(parents=True)
        status_file.write_text('{"phase": "completed", "agent_kind": "pi"}')
        status(branch="pi/x")


class TestAgentsHome:
    def test_uses_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path))
        assert _agents_home() == tmp_path

    def test_fallback_path_name(self, monkeypatch):
        monkeypatch.delenv("AGENTS_HOME", raising=False)
        with patch(
            "container_cli.commands.pi_agents.find_git_root",
            return_value=Path("/home/user/repo"),
        ):
            result = _agents_home()
        assert result == Path("/home/user/.worktrees")
