"""Image build and cleanup commands."""

from typing import Annotated

import typer

from container_cli.utils import run_make

app = typer.Typer(help="Image build commands")


@app.command()
def build(
    image: Annotated[str | None, typer.Option("--image", help="Image tag")] = None,
    dockerfile: Annotated[str | None, typer.Option("--dockerfile", help="Dockerfile path")] = None,
) -> None:
    """Build the container image (no cache)."""
    make_vars: dict[str, str] = {}
    if image:
        make_vars["IMAGE"] = image
    if dockerfile:
        make_vars["DOCKERFILE"] = dockerfile
    run_make("build", make_vars)


@app.command()
def clean() -> None:
    """Remove the container image."""
    run_make("clean")


@app.command(name="clean-network")
def clean_network() -> None:
    """Remove the bridge network."""
    run_make("clean-network")


@app.command(name="clean-all")
def clean_all() -> None:
    """Remove image and network."""
    run_make("clean-all")
