import os
import subprocess
import sys
from pathlib import Path

import typer


def find_git_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def makefile_dir() -> Path:
    return find_git_root() / "config"


def check_token() -> None:
    token = os.environ.get("CLAUDE_CONTAINER_OAUTH_TOKEN")
    if not token:
        typer.echo(
            "[error] CLAUDE_CONTAINER_OAUTH_TOKEN is not set — export it before running",
            err=True,
        )
        raise typer.Exit(1)


def run_make(target: str, extra_vars: dict[str, str] | None = None, *, tty: bool = False) -> None:
    vars_list = [f"{k}={v}" for k, v in (extra_vars or {}).items()]
    cmd = ["make", "-C", str(makefile_dir()), target, *vars_list]

    if tty:
        os.execvp(cmd[0], cmd)
    else:
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise typer.Exit(result.returncode)
