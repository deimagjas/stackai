from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from container_cli.utils import (
    agents_home,
    check_token,
    find_git_root,
    makefile_dir,
    print_agent_status,
    run_make,
    validate_branch,
    validate_task,
)

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
        with (
            patch(
                "container_cli.utils.subprocess.run",
                side_effect=subprocess.CalledProcessError(128, "git"),
            ),
            pytest.raises(subprocess.CalledProcessError),
        ):
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

    def test_exits_when_token_missing(self, monkeypatch: pytest.MonkeyPatch, capsys):
        monkeypatch.delenv("CLAUDE_CONTAINER_OAUTH_TOKEN", raising=False)
        with pytest.raises(typer.Exit) as exc_info:
            check_token()
        assert exc_info.value.exit_code == 1
        err = capsys.readouterr().err
        assert err.startswith("[error]")
        assert "CLAUDE_CONTAINER_OAUTH_TOKEN" in err

    def test_exits_when_token_empty(self, monkeypatch: pytest.MonkeyPatch, capsys):
        monkeypatch.setenv("CLAUDE_CONTAINER_OAUTH_TOKEN", "")
        with pytest.raises(typer.Exit) as exc_info:
            check_token()
        assert exc_info.value.exit_code == 1
        err = capsys.readouterr().err
        assert err.startswith("[error]")
        assert "CLAUDE_CONTAINER_OAUTH_TOKEN" in err


# ---------- run_make ----------


class TestRunMake:
    def test_basic_target(self, fake_git_root: Path):
        with (
            patch("container_cli.utils.os.execvp"),
            patch("container_cli.utils.subprocess.run", return_value=MagicMock(returncode=0)) as m,
        ):
            run_make("build")
            m.assert_called_once_with(["make", "-C", str(fake_git_root / "config"), "build"])

    def test_with_extra_vars(self, fake_git_root: Path):
        with (
            patch("container_cli.utils.os.execvp"),
            patch("container_cli.utils.subprocess.run", return_value=MagicMock(returncode=0)) as m,
        ):
            run_make("spawn", {"BRANCH": "feat/x", "TASK": "do stuff"})
            cmd = m.call_args[0][0]
            assert cmd[:4] == ["make", "-C", str(fake_git_root / "config"), "spawn"]
            assert "BRANCH=feat/x" in cmd
            assert "TASK=do stuff" in cmd

    def test_raises_exit_on_failure(self, fake_git_root: Path):
        with (
            patch("container_cli.utils.os.execvp"),
            patch("container_cli.utils.subprocess.run", return_value=MagicMock(returncode=2)),
        ):
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

    def test_default_tty_uses_subprocess(self, fake_git_root: Path):
        with (
            patch("container_cli.utils.os.execvp") as m_exec,
            patch(
                "container_cli.utils.subprocess.run", return_value=MagicMock(returncode=0)
            ) as m_sub,
        ):
            run_make("build")
            m_sub.assert_called_once()
            m_exec.assert_not_called()


# ---------- agents_home ----------


class TestAgentsHome:
    def test_uses_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path))
        assert agents_home() == tmp_path

    def test_fallback_path_name(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("AGENTS_HOME", raising=False)
        with patch("container_cli.utils.find_git_root", return_value=Path("/home/user/repo")):
            assert agents_home() == Path("/home/user/.worktrees")


# ---------- validate_branch ----------


class TestValidateBranch:
    @pytest.mark.parametrize(
        "branch",
        ["feat/foo", "pi/refactor", "fix/issue-42", "release/v1.2.3", "main", "feat_underscore"],
    )
    def test_accepts_normal_branch_names(self, branch: str):
        validate_branch(branch)  # should not raise

    @pytest.mark.parametrize(
        "branch",
        [
            "",
            "feat;rm -rf x",
            "feat && evil",
            "feat foo",
            "feat`id`",
            "feat$(id)",
            "feat\nbar",
            "../escape",
            "feat/../../escape",
            "-evil",
            "--upload-pack=evil",
            "/absolute",
            ".hidden",
        ],
    )
    def test_rejects_malicious_or_malformed_names(self, branch: str, capsys):
        with pytest.raises(typer.Exit) as exc_info:
            validate_branch(branch)
        assert exc_info.value.exit_code == 1
        err = capsys.readouterr().err
        assert "invalid branch" in err


# ---------- validate_task ----------


class TestValidateTask:
    @pytest.mark.parametrize(
        "task",
        ["implement feature X", "rename ambiguous helpers", "fix bug #42 (edge-case: 'quotes')"],
    )
    def test_accepts_normal_task_text(self, task: str):
        validate_task(task)  # should not raise

    @pytest.mark.parametrize(
        "task",
        ["", "line1\nline2", "task\rcarriage", "tab\there", "nul\x00byte"],
    )
    def test_rejects_empty_or_control_characters(self, task: str, capsys):
        with pytest.raises(typer.Exit) as exc_info:
            validate_task(task)
        assert exc_info.value.exit_code == 1
        err = capsys.readouterr().err
        assert "invalid task" in err


# ---------- print_agent_status ----------


class TestPrintAgentStatus:
    def test_exits_when_status_file_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path))
        with pytest.raises(typer.Exit) as exc_info:
            print_agent_status("feat-x", label="status")
        assert exc_info.value.exit_code == 1
        assert "[status] No status file found" in capsys.readouterr().out

    def test_prints_json_when_status_file_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path))
        status_file = tmp_path / "feat-x" / ".agent" / "status.json"
        status_file.parent.mkdir(parents=True)
        status_file.write_text('{"phase": "completed"}')
        print_agent_status("feat-x", label="status")
        assert "completed" in capsys.readouterr().out

    def test_label_tags_the_not_found_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path))
        with pytest.raises(typer.Exit):
            print_agent_status("feat-x", label="pi-status")
        assert "[pi-status]" in capsys.readouterr().out

    def test_rejects_branch_escaping_agents_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path / "worktrees"))
        outside = tmp_path / "outside" / ".agent" / "status.json"
        outside.parent.mkdir(parents=True)
        outside.write_text('{"phase": "completed"}')
        with pytest.raises(typer.Exit) as exc_info:
            print_agent_status("../outside", label="status")
        assert exc_info.value.exit_code == 1
        captured = capsys.readouterr()
        assert "invalid branch" in captured.err
        assert "completed" not in captured.out

    def test_allows_branch_with_slash_inside_agents_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ):
        monkeypatch.setenv("AGENTS_HOME", str(tmp_path))
        status_file = tmp_path / "feat" / "foo" / ".agent" / "status.json"
        status_file.parent.mkdir(parents=True)
        status_file.write_text('{"phase": "working"}')
        print_agent_status("feat/foo", label="status")
        assert "working" in capsys.readouterr().out
