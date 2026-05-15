from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from container_cli.commands.agents import (
    _agents_home,
    follow,
    list_agents,
    logs,
    spawn,
    status,
    stop,
)


class TestSpawn:
    def test_calls_check_token(self, mock_run_make, mock_check_token):
        spawn(branch="feat/a", task="build it", cpus=None, memory=None, image=None)
        mock_check_token["agents"].assert_called_once()

    def test_basic_spawn(self, mock_run_make, mock_check_token):
        spawn(branch="feat/a", task="build it", cpus=None, memory=None, image=None)
        mock_run_make["agents"].assert_called_once_with(
            "spawn", {"BRANCH": "feat/a", "TASK": "build it"}
        )

    def test_spawn_with_cpus(self, mock_run_make, mock_check_token):
        spawn(branch="b", task="t", cpus=4, memory=None, image=None)
        call_vars = mock_run_make["agents"].call_args[0][1]
        assert call_vars["CPUS"] == "4"

    def test_spawn_with_memory(self, mock_run_make, mock_check_token):
        spawn(branch="b", task="t", cpus=None, memory="8G", image=None)
        call_vars = mock_run_make["agents"].call_args[0][1]
        assert call_vars["MEMORY"] == "8G"

    def test_spawn_with_image(self, mock_run_make, mock_check_token):
        spawn(branch="b", task="t", cpus=None, memory=None, image="my-img:latest")
        call_vars = mock_run_make["agents"].call_args[0][1]
        assert call_vars["IMAGE"] == "my-img:latest"

    def test_spawn_all_optional_params(self, mock_run_make, mock_check_token):
        spawn(branch="b", task="t", cpus=2, memory="4G", image="img")
        call_vars = mock_run_make["agents"].call_args[0][1]
        assert call_vars == {
            "BRANCH": "b",
            "TASK": "t",
            "CPUS": "2",
            "MEMORY": "4G",
            "IMAGE": "img",
        }


class TestListAgents:
    def test_calls_run_make(self, mock_run_make):
        list_agents()
        mock_run_make["agents"].assert_called_once_with("list-agents")


class TestLogs:
    def test_passes_branch(self, mock_run_make):
        logs(branch="feat/x")
        mock_run_make["agents"].assert_called_once_with("logs-agent", {"BRANCH": "feat/x"})


class TestFollow:
    def test_passes_branch_with_tty(self, mock_run_make):
        follow(branch="feat/x")
        mock_run_make["agents"].assert_called_once_with(
            "follow-agent", {"BRANCH": "feat/x"}, tty=True
        )


class TestStop:
    def test_passes_branch(self, mock_run_make):
        stop(branch="feat/x")
        mock_run_make["agents"].assert_called_once_with("stop-agent", {"BRANCH": "feat/x"})


class TestStatus:
    def test_missing_status_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path))
        with pytest.raises(typer.Exit) as exc_info:
            status(branch="feat/x")
        assert exc_info.value.exit_code == 1

    def test_reads_status_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path))
        status_file = tmp_path / "feat/x" / ".agent" / "status.json"
        status_file.parent.mkdir(parents=True)
        status_file.write_text('{"phase": "running"}')
        status(branch="feat/x")

    def test_agents_home_fallback(self, monkeypatch):
        monkeypatch.delenv("AGENTS_HOME", raising=False)
        with (
            patch("container_cli.commands.agents.find_git_root", return_value=Path("/fake/repo")),
            pytest.raises(typer.Exit) as exc_info,
        ):
            status(branch="nonexistent-branch")
        assert exc_info.value.exit_code == 1


class TestAgentsHome:
    def test_uses_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path))
        assert _agents_home() == tmp_path

    def test_fallback_path_name(self, monkeypatch):
        monkeypatch.delenv("AGENTS_HOME", raising=False)
        with patch(
            "container_cli.commands.agents.find_git_root", return_value=Path("/home/user/repo")
        ):
            result = _agents_home()
        assert result == Path("/home/user/.worktrees")
