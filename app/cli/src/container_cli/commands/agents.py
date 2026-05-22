"""Agent lifecycle commands (spawn, list, logs, follow, stop, status, summary)."""

from typing import Annotated

import typer

from container_cli.targets import Target
from container_cli.utils import check_token, print_agent_status, run_make

app = typer.Typer(help="Agent lifecycle commands")


@app.command()
def spawn(
    branch: Annotated[str, typer.Option("--branch", help="Git branch for the agent worktree")],
    task: Annotated[str, typer.Option("--task", help="Task description for the agent")],
    cpus: Annotated[int | None, typer.Option("--cpus", help="CPU count")] = None,
    memory: Annotated[str | None, typer.Option("--memory", help="Memory limit (e.g. 12G)")] = None,
    image: Annotated[str | None, typer.Option("--image", help="Image tag")] = None,
) -> None:
    """Spawn a detached headless agent container."""
    check_token()
    make_vars: dict[str, str] = {"BRANCH": branch, "TASK": task}
    if cpus is not None:
        make_vars["CPUS"] = str(cpus)
    if memory:
        make_vars["MEMORY"] = memory
    if image:
        make_vars["IMAGE"] = image
    run_make(Target.SPAWN, make_vars)


@app.command(name="list")
def list_agents() -> None:
    """List active agent containers and worktrees."""
    run_make(Target.LIST_AGENTS)


@app.command()
def logs(
    branch: Annotated[str, typer.Option("--branch", help="Agent branch name")],
) -> None:
    """Show logs for a branch agent."""
    run_make(Target.LOGS_AGENT, {"BRANCH": branch})


@app.command()
def follow(
    branch: Annotated[str, typer.Option("--branch", help="Agent branch name")],
) -> None:
    """Follow live streaming logs for a branch agent."""
    run_make(Target.FOLLOW_AGENT, {"BRANCH": branch}, tty=True)


@app.command()
def stop(
    branch: Annotated[str, typer.Option("--branch", help="Agent branch name")],
) -> None:
    """Stop a branch agent container."""
    run_make(Target.STOP_AGENT, {"BRANCH": branch})


@app.command()
def status(
    branch: Annotated[str, typer.Option("--branch", help="Agent branch name")],
) -> None:
    """Show agent status from persisted status.json file."""
    print_agent_status(branch, label="status")


@app.command()
def summary(
    branch: Annotated[str, typer.Option("--branch", help="Agent branch name")],
) -> None:
    """Show structured lifecycle events for a branch agent."""
    run_make(Target.SUMMARY_AGENT, {"BRANCH": branch})
