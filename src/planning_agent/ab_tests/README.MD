# AB Tests Readme

## Directory Overview

This repository contains various AB tests designed to evaluate different
approaches for enhancing the Planning Agent's performance and efficiency.
The testing focuses on distinct aspects of the agent, with specific
emphasis on tool filtering and alternative planning methodologies.

## Folder Structure

- **filter_tests**: Contains experiments aimed at assessing various tool
  filtering techniques from an MCP composer instance. Detailed summaries can
  be found in `filter_test_summary.md`. To run these tests, ensure you have
  an MCP composer instance running in a separate terminal and execute the
  command `uv run src/planning_agent/filter_tests/filter_test.py`.
- **executing_without_plan**: This folder stores alternative code snippets that can be
  integrated into the Planning Agent's workflow to evaluate its performance
  without a planning phase. Currently, these are placeholders
  for future development and testing purposes.

## Running Tests

1. **Filter Tests**: - Ensure an MCP composer instance is operational in another terminal
   window. - Navigate to `filter_tests` within this repository. - Execute the test using: `uv run 
src/planning_agent/filter_tests/filter_test.py`.

2. **No Planning Phase Tests**: - Currently, this folder serves as a storage area for alternative code
   snippets intended for testing a planning-less agent workflow. Actual
   execution is not implemented at present but will be in future iterations
   to assess performance without a dedicated planning phase.
