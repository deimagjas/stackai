from pytest_bdd import given, parsers, scenarios

from tests.acceptance.steps.common_steps import *  # noqa: F401, F403


@given(parsers.parse(
    'a PI status file exists for branch "{branch}" with payload {payload}'
))
def _pi_status_file_exists(invocation_context, branch: str, payload: str) -> None:
    status_dir = invocation_context.agents_home / branch / ".agent"
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "status.json").write_text(payload)


scenarios("../features/pi_agents.feature")
