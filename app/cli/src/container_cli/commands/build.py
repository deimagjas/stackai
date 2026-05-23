"""Image build and cleanup commands.

These functions are registered as top-level commands by `container_cli.main`.
"""

from typing import Annotated

import typer

from container_cli.targets import Target
from container_cli.utils import run_make


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
    run_make(Target.BUILD, make_vars)


def clean() -> None:
    """Remove the container image."""
    run_make(Target.CLEAN)


def clean_network() -> None:
    """Remove the bridge network."""
    run_make(Target.CLEAN_NETWORK)


def clean_all() -> None:
    """Remove image and network."""
    run_make(Target.CLEAN_ALL)
