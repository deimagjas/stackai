"""Single source of truth for the config/Makefile targets the q CLI invokes.

Centralising the target names here turns the implicit, scattered functional
coupling between the CLI and the orchestration Makefile into one explicit
contract: a renamed target now has a single Python counterpart to update, and
``tests/test_targets.py`` verifies every member against the real Makefile.

``Target`` is a ``StrEnum``, so each member compares equal to its string value
and can be passed anywhere a plain target string is expected.
"""

from enum import StrEnum


class Target(StrEnum):
    """Names of the config/Makefile targets invoked through ``utils.run_make``."""

    # Image build and cleanup.
    BUILD = "build"
    CLEAN = "clean"
    CLEAN_NETWORK = "clean-network"
    CLEAN_ALL = "clean-all"

    # Bridge network.
    NETWORK = "network"

    # Interactive coordinator container.
    RUN = "run"
    SHELL = "shell"

    # Claude agent lifecycle.
    SPAWN = "spawn"
    LIST_AGENTS = "list-agents"
    LOGS_AGENT = "logs-agent"
    FOLLOW_AGENT = "follow-agent"
    STOP_AGENT = "stop-agent"
    SUMMARY_AGENT = "summary-agent"

    # PI agent lifecycle (local mlx_lm backend).
    BUILD_PI = "build-pi"
    SPAWN_PI = "spawn-pi"
    LIST_PI_AGENTS = "list-pi-agents"
    LOGS_PI_AGENT = "logs-pi-agent"
    FOLLOW_PI_AGENT = "follow-pi-agent"
    STOP_PI_AGENT = "stop-pi-agent"
