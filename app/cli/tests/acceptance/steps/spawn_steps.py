from pytest_bdd import scenarios

from tests.acceptance.steps.common_steps import *  # noqa: F401, F403

scenarios("../features/spawn.feature")
