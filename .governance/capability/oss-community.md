# Capability: open-source community process

Follows the FastMCP contribution model for the public MCP Composer repository.

- A clear issue with a reproduction is a contribution. Merged fixes credit the reporter with `Co-authored-by`.
- Pull requests use `Fixes` / `Closes` / `Resolves` and an issue number. Large features wait for agreement on the issue.
- License is Apache 2.0. There is no CODEOWNERS or MAINTAINERS file; GitHub Direct access is authoritative. Conduct reports go privately to community leaders, not a public issue.
- Vulnerabilities go to GitHub Security Advisories. Do not file them as public issues.
- Default checks: `uv run pytest tests/unit` from `modules/mcp_composer`.
