from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from container_cli.utils import check_token, find_git_root, makefile_dir, run_make


# ---------- find_git_root ----------

class TestFindGitRoot:
    def test_returns_path_from_git(self):
        mock_result = MagicMock(stdout="/home/user/repo\n")
        with patch("container_cli.utils.subprocess.run", return_value=mock_result) as m:
            root = find_git_root()
            m.assert_called_once_with(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            assert root == Path("/home/user/repo")

    def test_strips_whitespace(self):
        mock_result = MagicMock(stdout="  /tmp/repo  \n")
        with patch("container_cli.utils.subprocess.run", return_value=mock_result):
            assert find_git_root() == Path("/tmp/repo")

    def test_raises_on_git_failure(self):
        with patch(
            "container_cli.utils.subprocess.run",
            side_effect=subprocess.CalledProcessError(128, "git"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                find_git_root()


# ---------- makefile_dir ----------

class TestMakefileDir:
    def test_returns_config_subdir(self, fake_git_root: Path):
        assert makefile_dir() == fake_git_root / "config"


# ---------- check_token ----------

class TestCheckToken:
    def test_passes_when_token_set(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("CLAUDE_CONTAINER_OAUTH_TOKEN", "tok-abc")
        check_token()  # should not raise

    def test_exits_when_token_missing(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("CLAUDE_CONTAINER_OAUTH_TOKEN", raising=False)
        with pytest.raises(typer.Exit) as exc_info:
            check_token()
        assert exc_info.value.exit_code == 1

    def test_exits_when_token_empty(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("CLAUDE_CONTAINER_OAUTH_TOKEN", "")
        with pytest.raises(typer.Exit) as exc_info:
            check_token()
        assert exc_info.value.exit_code == 1


# ---------- run_make ----------

class TestRunMake:
    def test_basic_target(self, fake_git_root: Path):
        with patch("container_cli.utils.subprocess.run", return_value=MagicMock(returncode=0)) as m:
            run_make("build")
            m.assert_called_once_with(
                ["make", "-C", str(fake_git_root / "config"), "build"]
            )

    def test_with_extra_vars(self, fake_git_root: Path):
        with patch("container_cli.utils.subprocess.run", return_value=MagicMock(returncode=0)) as m:
            run_make("spawn", {"BRANCH": "feat/x", "TASK": "do stuff"})
            cmd = m.call_args[0][0]
            assert cmd[:4] == ["make", "-C", str(fake_git_root / "config"), "spawn"]
            assert "BRANCH=feat/x" in cmd
            assert "TASK=do stuff" in cmd

    def test_raises_exit_on_failure(self, fake_git_root: Path):
        with patch("container_cli.utils.subprocess.run", return_value=MagicMock(returncode=2)):
            with pytest.raises(typer.Exit) as exc_info:
                run_make("build")
            assert exc_info.value.exit_code == 2

    def test_tty_mode_uses_execvp(self, fake_git_root: Path):
        with patch("container_cli.utils.os.execvp") as m_exec:
            run_make("run", tty=True)
            m_exec.assert_called_once()
            args = m_exec.call_args
            assert args[0][0] == "make"
            assert "run" in args[0][1]

    def test_tty_mode_passes_extra_vars(self, fake_git_root: Path):
        with patch("container_cli.utils.os.execvp") as m_exec:
            run_make("shell", {"NAME": "test"}, tty=True)
            cmd = m_exec.call_args[0][1]
            assert "NAME=test" in cmd
