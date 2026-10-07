# OSS community files (2026-10-07)

Public release shape for `github.com/ibm/mcp-composer`, following the FastMCP contribution model.

## Community files

- `CONTRIBUTING.md` — issue-first reports, pull requests link an issue, Apache 2.0, agent note
- `AGENTS.md` — checks and security contracts for agent authors
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.0
- `SECURITY.md` — GitHub private advisories; bind and stdio allowlist are the security boundaries
- `NOTICE`, `CHANGELOG.md`
- `.github/ISSUE_TEMPLATE`, pull request template, `release.yml`, Dependabot
- `.github/workflows/ci.yml` runs `tests/unit` on Python 3.11–3.13
- `.github/workflows/publish.yaml` builds the wheel with uv and attaches it to the GitHub release

## Tests

- `tests/unit`: 1189 passed
- Adjacent non-e2e modules (`test_policy`, `test_postgres`, `test_main_module`, tracing, composer scripts): 17 passed, 1 skipped
- Removed collection failures: `tests/test_cli.py` and `tests/test_main.py` imported `mcp_composer.core.utils.cli`, which is gone. CLI coverage lives in `tests/unit/test_cli_typer.py`
- `tests/test_composer_oauth_provider.py` was a manual script. It now lives at `modules/mcp_composer/examples/oauth_provider_manual.py`
- `tests/e2e` still needs a running server and is outside the default suite

## Public docs

- Root README no longer documents internal cluster hosts or a private chatbot UI
- Docs footer license corrected from MIT to Apache 2.0
- VitePress `base` is `/mcp-composer/` for `ibm.github.io`
- Sample OAuth URLs use `https://example.com` instead of IBM preprod SSO
- Ruff still reports existing findings, so CI gates on the unit suite. Contributors fix ruff on the lines they change

## Before the public push

- Confirm `github.com/ibm/mcp-composer` exists and Security Advisories are enabled
- No `CODEOWNERS` or `MAINTAINERS.md`. GitHub Direct access is authoritative; public docs do not list maintainers
- Publish screenshots that used to live on the internal GitHub host
