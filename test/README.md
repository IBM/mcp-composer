# Testing Guide

This project uses [pytest](https://pytest.org/) for both unit and end-to-end (E2E) testing.

## Structure

- `unit/` — Unit tests for individual functions or classes
- `e2e/` — End-to-end tests simulating full workflows or CLI/API calls

## Why E2E Testing?

End-to-end (E2E) tests are designed to validate the system as a whole, ensuring that all components (APIs, tools, member servers, config, and orchestration) work together as expected. E2E tests:

- Simulate real user/API interactions
- Catch integration issues that unit tests cannot
- Ensure that tools are discoverable and callable via the API
- Validate dynamic configuration, registration, and orchestration flows
- Provide confidence that deployments will work in real-world scenarios

E2E tests complement unit tests by covering the "big picture" and verifying that the system behaves correctly from the outside in.

## How E2E Tests Are Designed

- E2E tests launch the MCPComposer FastAPI app in a subprocess, using real or example configs.
- They wait for the server to be ready, then interact with it via HTTP (using `requests`).
- Tests cover:
  - Health checks (is the API up?)
  - Tool discovery (are all tools registered and callable?)
  - Tool invocation (do tools respond to valid/invalid input?)
  - Management flows (register, update, activate, deactivate, delete servers)
  - Integration with real external APIs (e.g., GraphQL endpoints)
- Tests are robust to timing issues and clean up after themselves.
- You can add more E2E tests for new endpoints, workflows, or integration scenarios.

## Running Tests

To run all tests:

```
pytest
```

To run only unit tests:

```
pytest unit/
```

To run only E2E tests:

```
pytest e2e/
```

## Notes
- Make sure pytest is installed: `pip install pytest`
- E2E tests may require network access for external APIs.
- You can extend E2E tests by adding new files in `test/e2e/` following the provided examples. 