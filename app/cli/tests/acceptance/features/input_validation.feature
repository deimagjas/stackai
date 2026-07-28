Feature: Input validation for branch and task arguments
  As a user of the q CLI
  I want malformed or malicious branch/task values rejected before reaching make
  So that shell injection and path traversal cannot reach the host

  Background:
    Given the make runner is ready

  Scenario: Spawn rejects a branch with shell metacharacters
    Given the CLAUDE_CONTAINER_OAUTH_TOKEN is set
    When I run "q spawn --branch 'feat;rm -rf x' --task implement-x"
    Then the command exits with an error
    And the output contains "invalid branch"
    And the make runner was not invoked

  Scenario: Spawn rejects a branch with path traversal
    Given the CLAUDE_CONTAINER_OAUTH_TOKEN is set
    When I run "q spawn --branch ../../escape --task implement-x"
    Then the command exits with an error
    And the output contains "invalid branch"
    And the make runner was not invoked

  Scenario: Spawn rejects a task containing control characters
    Given the CLAUDE_CONTAINER_OAUTH_TOKEN is set
    When I run spawn with a task containing a control character
    Then the command exits with an error
    And the output contains "invalid task"
    And the make runner was not invoked

  Scenario: Agent status rejects a branch that escapes the worktrees directory
    When I run "q agents status --branch ../../../etc"
    Then the command exits with an error
    And the output contains "invalid branch"
    And the make runner was not invoked

  Scenario: Stop rejects a branch that begins with a dash
    When I run "q agents stop --branch=-evil"
    Then the command exits with an error
    And the output contains "invalid branch"
    And the make runner was not invoked

  Scenario: PI spawn rejects a branch with shell metacharacters
    When I run "q pi spawn --branch 'pi;evil' --task implement-x"
    Then the command exits with an error
    And the output contains "invalid branch"
    And the make runner was not invoked
