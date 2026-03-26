# shellcheck shell=sh

# Defining variables and functions here will affect all specfiles.
set -eu

spec_helper_precheck() {
  : minimum_version "0.28.1"
}

spec_helper_loaded() {
  :
}

spec_helper_configure() {
  : import 'support/custom_matcher'
}

# ── Common mock setup ─────────────────────────────────────────────────────────

# Stub that records calls for later assertions.
# Usage: setup_mock <cmd_name>
# Creates a shell function <cmd_name> that appends "$cmd_name <args>" to
# the variable MOCK_CALLS (newline-separated).
setup_mock() {
  : # individual specs define their own mocks via shellspec helpers
}
