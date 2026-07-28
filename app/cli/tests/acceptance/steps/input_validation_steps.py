from pytest_bdd import scenarios, then, when

from container_cli.main import app
from tests.acceptance.steps.common_steps import *  # noqa: F401, F403

scenarios("../features/input_validation.feature")


@when("I run spawn with a task containing a control character")
def _spawn_with_control_char_task(invocation_context) -> None:
    invocation_context.result = invocation_context.runner.invoke(
        app, ["spawn", "--branch", "feat/ok", "--task", "do this\nrm -rf x"]
    )


@then("the make runner was not invoked")
def _make_runner_not_invoked(invocation_context) -> None:
    for name, mock in invocation_context.mocks.items():
        assert not mock.called, f"run_make mock {name!r} was invoked: {mock.call_args_list}"
