Feature: Build and clean container images
  As a user of the q CLI
  I want to build and clean images
  So that I can manage container artifacts

  Background:
    Given the make runner is ready

  Scenario: Build with defaults
    When I run "q build"
    Then the command exits successfully
    And the make runner was invoked with target "build"

  Scenario: Build with custom image and dockerfile
    When I run "q build --image my-img:1.0 --dockerfile Dockerfile.custom"
    Then the command exits successfully
    And the make vars include IMAGE="my-img:1.0" and DOCKERFILE="Dockerfile.custom"

  Scenario: Clean everything
    When I run "q clean-all"
    Then the command exits successfully
    And the make runner was invoked with target "clean-all"
