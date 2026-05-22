from __future__ import annotations

import re
from pathlib import Path

from container_cli.targets import Target

_TARGET_DEF = re.compile(r"^([a-zA-Z0-9_-]+):", re.MULTILINE)


def _find_makefile() -> Path:
    """Locate config/Makefile by walking up from this test file.

    Walking up (rather than a fixed parent index) keeps the lookup correct when
    the test runs from the mutmut copy under ``mutants/``.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "config" / "Makefile"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("config/Makefile not found in any parent directory")


_MAKEFILE = _find_makefile()


class TestTargetValues:
    def test_every_member_value_is_kebab_case(self):
        for target in Target:
            assert re.fullmatch(r"[a-z][a-z-]*", target.value), target

    def test_member_equals_its_string_value(self):
        assert Target.SPAWN == "spawn"
        assert Target.LIST_AGENTS == "list-agents"
        assert Target.SPAWN_PI == "spawn-pi"

    def test_no_duplicate_values(self):
        values = [t.value for t in Target]
        assert len(values) == len(set(values))


class TestMakefileContract:
    def test_every_target_exists_in_the_makefile(self):
        defined = set(_TARGET_DEF.findall(_MAKEFILE.read_text()))
        missing = {t.value for t in Target} - defined
        assert not missing, f"Target members absent from config/Makefile: {sorted(missing)}"
