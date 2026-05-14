from __future__ import annotations

import re
import shlex

from pytest_bdd import given, parsers, then, when

from container_cli.main import app

_VAR_PATTERN = re.compile(r'(\w+)="([^"]*)"')


def _parse_vars(text: str) -> dict[str, str]:
    return dict(_VAR_PATTERN.findall(text))


@given("the make runner is ready")
def _make_runner_ready(invocation_context) -> None:
    """No-op — referencing invocation_context activates the mock fixture."""


@given("the CLAUDE_CONTAINER_OAUTH_TOKEN is set")
def _token_set(invocation_context) -> None:
    invocation_context.monkeypatch.setenv("CLAUDE_CONTAINER_OAUTH_TOKEN", "test-token-123")


@given("the CLAUDE_CONTAINER_OAUTH_TOKEN is not set")
def _token_not_set(invocation_context) -> None:
    invocation_context.monkeypatch.delenv("CLAUDE_CONTAINER_OAUTH_TOKEN", raising=False)


@when(parsers.parse('I run "{cmdline}"'))
def _invoke_cli(invocation_context, cmdline: str) -> None:
    args = shlex.split(cmdline)
    if args and args[0] == "q":
        args = args[1:]
    invocation_context.result = invocation_context.runner.invoke(app, args)


@then("the command exits successfully")
def _exits_successfully(invocation_context) -> None:
    result = invocation_context.result
    assert result is not None, "no CLI invocation recorded"
    assert result.exit_code == 0, f"exit_code={result.exit_code}, output={result.output!r}"


@then("the command exits with an error")
def _exits_with_error(invocation_context) -> None:
    result = invocation_context.result
    assert result is not None, "no CLI invocation recorded"
    assert result.exit_code != 0, f"expected non-zero exit, got 0; output={result.output!r}"


@then(parsers.parse('the make runner was invoked with target "{target}"'))
def _make_invoked_with_target(invocation_context, target: str) -> None:
    targets_called: list[str] = []
    for mock in invocation_context.mocks.values():
        for call in mock.call_args_list:
            if call.args:
                targets_called.append(call.args[0])
    assert target in targets_called, f"target {target!r} not in {targets_called}"


@then(parsers.parse("the make vars include {vars_text}"))
def _make_vars_include(invocation_context, vars_text: str) -> None:
    expected = _parse_vars(vars_text)
    assert expected, f'no KEY="value" pairs parsed from {vars_text!r}'
    var_dicts: list[dict] = []
    for mock in invocation_context.mocks.values():
        for call in mock.call_args_list:
            if len(call.args) >= 2 and isinstance(call.args[1], dict):
                var_dicts.append(call.args[1])
    matched = any(all(d.get(k) == v for k, v in expected.items()) for d in var_dicts)
    assert matched, f"expected {expected} in one of {var_dicts}"


@then(parsers.parse('the output contains "{text}"'))
def _output_contains(invocation_context, text: str) -> None:
    assert text in invocation_context.result.output, (
        f"{text!r} not in {invocation_context.result.output!r}"
    )


@then("the output mentions the missing token")
def _output_missing_token(invocation_context) -> None:
    assert "CLAUDE_CONTAINER_OAUTH_TOKEN" in invocation_context.result.output
