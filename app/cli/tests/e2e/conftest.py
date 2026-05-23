"""Shared fixtures and collection gating for the opt-in end-to-end tests.

These tests spawn real Apple Container CLI containers, so they are:

* **local-only** — GitHub Actions has no Apple Container CLI;
* **opt-in** — collected only when ``STACKAI_E2E=1`` is exported;
* **slow and billable** — the Claude round-trip spends real Claude credits.

Run them with ``make e2e-test`` (from ``app/cli/``), which exports the gate
variable. Without it, pytest never imports the test modules, so the default
``uv run pytest`` and the mutmut suite ignore them entirely.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

# Collection gate: without STACKAI_E2E=1, pytest skips collecting these modules.
collect_ignore_glob = [] if os.environ.get("STACKAI_E2E") == "1" else ["test_*.py"]

# Terminal phases written by config/entrypoint*.sh into .agent/status.json.
_TERMINAL_PHASES = frozenset({"completed", "errored"})


def _run_q(*args: str, timeout: float = 600) -> subprocess.CompletedProcess[str]:
    """Invoke the real q CLI in a subprocess, inheriting the current environment."""
    return subprocess.run(
        [sys.executable, "-m", "container_cli.main", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _image_present(image: str) -> bool | None:
    """Report whether a container image exists locally.

    Returns:
        True or False when the Apple Container CLI answers, None when the
        command is unavailable so the caller should not skip on that basis.
    """
    result = subprocess.run(
        ["container", "image", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return image.split(":")[0] in result.stdout


@pytest.fixture()
def run_q() -> Callable[..., subprocess.CompletedProcess[str]]:
    """Return a helper that runs the q CLI and captures its output."""
    return _run_q


@pytest.fixture()
def require_container_cli() -> None:
    """Skip the test unless the Apple `container` CLI is on PATH."""
    if shutil.which("container") is None:
        pytest.skip("Apple Container CLI ('container') not found — E2E needs macOS 26+ ARM64")


@pytest.fixture()
def require_claude_token() -> None:
    """Skip the test unless a Claude container OAuth token is exported."""
    if not os.environ.get("CLAUDE_CONTAINER_OAUTH_TOKEN"):
        pytest.skip("CLAUDE_CONTAINER_OAUTH_TOKEN not set — required to spawn a Claude agent")


@pytest.fixture()
def require_claude_image() -> None:
    """Skip the test unless the claude-agent:wolfi image is built."""
    if _image_present("claude-agent:wolfi") is False:
        pytest.skip("image claude-agent:wolfi not built — run `q build` first")


@pytest.fixture()
def require_pi_image() -> None:
    """Skip the test unless the claude-pi:ubuntu image is built."""
    if _image_present("claude-pi:ubuntu") is False:
        pytest.skip("image claude-pi:ubuntu not built — run `q pi build` first")


def _http_ok(url: str, *, timeout: float) -> bool:
    """Tiny probe — True when the URL responds 200."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _mlx_url() -> str:
    return os.environ.get("STACKAI_E2E_MLX_URL", "http://localhost:8080/v1/models")


@pytest.fixture(scope="session")
def _mlx_server_lifecycle() -> Iterator[subprocess.Popen[bytes] | None]:
    """Optionally spawn mlx_lm.server for the duration of the e2e session.

    Activated by exporting ``STACKAI_E2E_AUTOSTART_MLX=1``. Without that flag,
    or when a server is already reachable on the expected URL, this is a no-op
    — tests still see whatever process the user manages out of band.

    The exact invocation mirrors the parameters the PI agent expects (no
    coupling to the `iac` CLI: the e2e suite must run standalone). First-run
    cost is significant — model download + warmup can take several minutes;
    raise the wait ceiling with ``STACKAI_E2E_MLX_BOOT_TIMEOUT`` if needed.
    """
    if os.environ.get("STACKAI_E2E_AUTOSTART_MLX") != "1":
        yield None
        return

    url = _mlx_url()
    if _http_ok(url, timeout=2):
        # Pre-existing server (e.g. started via `uv run iac server start`) —
        # leave it alone so manual setups survive teardown.
        yield None
        return

    # conftest.py lives at app/cli/tests/e2e/ → repo root is parents[4].
    iac_dir = Path(__file__).resolve().parents[4] / "iac"
    cmd = [
        "uv", "run", "--directory", str(iac_dir), "mlx_lm.server",
        "--model", "mlx-community/gemma-4-26b-a4b-it-4bit",
        "--host", "0.0.0.0",
        "--port", "8080",
        "--prompt-cache-size", "5",
        "--prompt-cache-bytes", "6GB",
        "--decode-concurrency", "4",
        "--prompt-concurrency", "2",
        "--prefill-step-size", "1024",
        "--temp", "0.9",
        "--top-p", "0.95",
        "--top-k", "40",
        "--min-p", "0.0",
        "--max-tokens", "2048",
        "--use-default-chat-template",
        "--log-level", "INFO",
    ]

    log_path = Path(tempfile.gettempdir()) / "stackai-e2e-mlx.log"
    log_handle = log_path.open("ab")
    print(f"\n[mlx] starting mlx_lm.server (logs: {log_path})", flush=True)
    proc = subprocess.Popen(  # noqa: S603 — fixed argv, no shell.
        cmd,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    try:
        timeout = float(os.environ.get("STACKAI_E2E_MLX_BOOT_TIMEOUT", "600"))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"mlx_lm.server exited during startup (code {proc.returncode});"
                    f" see {log_path}"
                )
            if _http_ok(url, timeout=2):
                break
            time.sleep(3)
        else:
            proc.terminate()
            raise TimeoutError(
                f"mlx_lm.server did not become reachable at {url} within"
                f" {timeout}s; see {log_path}"
            )
        print(f"[mlx] ready on {url}", flush=True)
        yield proc
    finally:
        log_handle.close()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


@pytest.fixture()
def require_mlx_server(_mlx_server_lifecycle) -> None:
    """Skip the test unless the local mlx_lm.server is reachable on the host.

    Composes with ``_mlx_server_lifecycle`` so when the autostart env var is
    set, the server is already up by the time this check runs.
    """
    url = _mlx_url()
    if _http_ok(url, timeout=5):
        return
    pytest.skip(
        f"mlx_lm.server unreachable at {url} — run `uv run iac server start`"
        " or set STACKAI_E2E_AUTOSTART_MLX=1 to let the suite spawn it"
    )


@pytest.fixture()
def isolated_agents_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point AGENTS_HOME at a throwaway directory for the duration of the test."""
    home = tmp_path / "worktrees"
    home.mkdir()
    monkeypatch.setenv("AGENTS_HOME", str(home))
    return home


@pytest.fixture()
def unique_branch() -> str:
    """A collision-free, flat branch name (no slashes — see docs/agents/cli.md)."""
    return f"e2e-{int(time.time())}-{os.getpid()}"


@pytest.fixture()
def wait_for_terminal_phase() -> Callable[..., dict]:
    """Return a poller that blocks until an agent writes a terminal status.json."""

    def _wait(agents_home: Path, branch: str, timeout: float = 600) -> dict:
        status_file = agents_home / branch / ".agent" / "status.json"
        deadline = time.monotonic() + timeout
        last_phase = "<no status.json>"
        while time.monotonic() < deadline:
            if status_file.exists():
                try:
                    data = json.loads(status_file.read_text())
                except json.JSONDecodeError:
                    data = {}
                last_phase = data.get("phase", "<unparsed>")
                if last_phase in _TERMINAL_PHASES:
                    return data
            time.sleep(5)
        raise AssertionError(
            f"agent '{branch}' did not reach a terminal phase within {timeout}s "
            f"(last phase seen: {last_phase})"
        )

    return _wait


@pytest.fixture()
def agent_cleanup(isolated_agents_home: Path) -> Iterator[Callable[..., None]]:
    """Register (branch, kind) pairs to be stopped and pruned after the test."""
    registered: list[tuple[str, str]] = []

    def _register(branch: str, kind: str = "claude") -> None:
        registered.append((branch, kind))

    yield _register

    for branch, kind in registered:
        stop = ["pi", "stop"] if kind == "pi" else ["agents", "stop"]
        _run_q(*stop, "--branch", branch, timeout=120)
        worktree = isolated_agents_home / branch
        for cmd in (
            ["git", "worktree", "remove", "--force", str(worktree)],
            ["git", "worktree", "prune"],
            ["git", "branch", "-D", branch],
        ):
            subprocess.run(cmd, capture_output=True, text=True, check=False)
