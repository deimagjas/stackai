"""Shared helpers: git/worktree paths, the Makefile runner, token and status I/O."""

import json
import os
import subprocess
from pathlib import Path

import typer

from container_cli.targets import Target


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
        typer.Exit: With code 1 when no status file exists for the branch.
    """
    status_file = agents_home() / branch / ".agent" / "status.json"
    if not status_file.exists():
        typer.echo(f"[{label}] No status file found for branch '{branch}'.")
        typer.echo(f"[{label}] Expected at: {status_file}")
        raise typer.Exit(1)

    data = json.loads(status_file.read_text())
    typer.echo(json.dumps(data, indent=2))
