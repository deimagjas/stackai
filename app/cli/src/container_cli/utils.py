"""Shared helpers: git/worktree paths, the Makefile runner, token and status I/O."""

import json
import os
import re
import subprocess
from pathlib import Path

import typer

from container_cli.targets import Target

# Branch names must start with an alphanumeric and use only safe characters,
# so a value can never be parsed as a flag (leading `-`), an absolute path
# (leading `/`), or a shell word boundary once it reaches make/git.
_BRANCH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")


def find_git_root() -> Path:
    """Return the absolute path of the repository root.

    Returns:
        Path to the top-level directory reported by `git rev-parse --show-toplevel`.

    Raises:
        subprocess.CalledProcessError: If the current working directory is not inside
            a git repository.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def makefile_dir() -> Path:
    """Return the directory that contains the orchestration Makefile.

    Returns:
        Path to `config/` under the git root.
    """
    return find_git_root() / "config"


def agents_home() -> Path:
    """Return the directory that holds agent worktrees.

    Returns:
        The `AGENTS_HOME` environment variable when set, otherwise a sibling
        `.worktrees/` directory next to the repository root.
    """
    env_val = os.environ.get("AGENTS_HOME")
    if env_val:
        return Path(env_val)
    return find_git_root().parent / ".worktrees"


def validate_branch(branch: str) -> None:
    """Reject branch names that could be misinterpreted by make, git, or the shell.

    Args:
        branch: Candidate git branch name received from the CLI.

    Raises:
        typer.Exit: With code 1 when the name is empty, contains `..`, or has
            characters outside `[A-Za-z0-9._/-]` (or does not start with an
            alphanumeric character).
    """
    if not branch or ".." in branch or not _BRANCH_RE.fullmatch(branch):
        typer.echo(f"[error] invalid branch name: {branch!r}", err=True)
        raise typer.Exit(1)


def validate_task(task: str) -> None:
    """Reject task descriptions that could smuggle control characters to the host.

    Args:
        task: Task prompt text received from the CLI.

    Raises:
        typer.Exit: With code 1 when the task is empty or contains control
            characters (newlines, carriage returns, tabs, NUL, DEL).
    """
    if not task or any(ord(char) < 32 or ord(char) == 127 for char in task):
        typer.echo(
            "[error] invalid task: must be non-empty and contain no control characters",
            err=True,
        )
        raise typer.Exit(1)


def check_token() -> None:
    """Verify that the Claude container OAuth token is exported.

    Raises:
        typer.Exit: With code 1 if `CLAUDE_CONTAINER_OAUTH_TOKEN` is unset or empty.
    """
    token = os.environ.get("CLAUDE_CONTAINER_OAUTH_TOKEN")
    if not token:
        typer.echo(
            "[error] CLAUDE_CONTAINER_OAUTH_TOKEN is not set — export it before running",
            err=True,
        )
        raise typer.Exit(1)


def run_make(
    target: Target, extra_vars: dict[str, str] | None = None, *, tty: bool = False
) -> None:
    """Invoke a Makefile target inside the project's `config/` directory.

    Args:
        target: The Makefile target to execute (a `Target` member, which is a
            `StrEnum` and therefore usable directly as the make argument).
        extra_vars: Optional mapping of variables passed as `KEY=VALUE` to make.
        tty: If True, replace the current process with `make` so it inherits the TTY
            (used by interactive commands like `run` and `follow`).

    Raises:
        typer.Exit: When the subprocess returns a non-zero exit code (non-TTY path).
    """
    vars_list = [f"{k}={v}" for k, v in (extra_vars or {}).items()]
    cmd = ["make", "-C", str(makefile_dir()), target, *vars_list]

    if tty:
        os.execvp(cmd[0], cmd)
    else:
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise typer.Exit(result.returncode)


def print_agent_status(branch: str, *, label: str) -> None:
    """Print the persisted `status.json` for an agent worktree branch.

    Args:
        branch: The agent branch whose status should be displayed.
        label: Tag used in the not-found messages (e.g. `status`, `pi-status`).

    Raises:
        typer.Exit: With code 1 when the branch resolves outside the worktrees
            directory or no status file exists for the branch.
    """
    base = agents_home().resolve()
    status_file = (agents_home() / branch / ".agent" / "status.json").resolve()
    if base not in status_file.parents:
        typer.echo(f"[{label}] invalid branch path: {branch!r}", err=True)
        raise typer.Exit(1)
    if not status_file.exists():
        typer.echo(f"[{label}] No status file found for branch '{branch}'.")
        typer.echo(f"[{label}] Expected at: {status_file}")
        raise typer.Exit(1)

    data = json.loads(status_file.read_text())
    typer.echo(json.dumps(data, indent=2))
