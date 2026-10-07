# Contributing to MCP Composer

Identifying a real problem is often the most valuable contribution you can make. A clear issue with a reproducible bug or a concrete use case is a contribution on its own. If it leads to a merged change implemented by a maintainer, you receive contributor credit for that change.

Participation follows our [Code of Conduct](CODE_OF_CONDUCT.md). Maintainers are listed in the [README](README.md#project). Report vulnerabilities privately through [SECURITY.md](SECURITY.md). Contributions are licensed under [Apache 2.0](LICENSE).

Agents should also read [AGENTS.md](AGENTS.md).

## Choose a contribution

A useful bug report states the problem, includes a minimal reproducible example, and explains the expected behavior. Search existing issues and pull requests first, including closed ones.

Simple, scoped bug fixes and documentation improvements are welcome. Enhancements need a maintainer-approved design in an issue before a large implementation. Third-party product integrations generally belong in a separate package.

MCP Composer prioritizes readable Python, clear APIs, and fixes at the source of a problem. A working implementation can still be unsuitable if it changes an intentional contract or adds a workaround the project must maintain indefinitely.

### Issues and pull requests

Every pull request must reference a tracked issue with an auto-close keyword (`Fixes #123`, `Closes #123`, or `Resolves #123`). If there is no issue, open one first. This lets maintainers deconflict effort and agree on the approach before a large change is written.

You can open a linked pull request for a small bug fix or doc change before a maintainer replies. Feature and integration pull requests should wait until a maintainer has agreed with the direction in the issue. A pull request without an issue link will not be reviewed until the link is added.

Do not post comments only to claim an issue. A concise report, a scoped linked pull request, or a substantive design discussion gives maintainers something concrete to evaluate.

### Contributor credit

If your issue leads to a merged change implemented by a maintainer, we credit you as a contributor to that change. This applies to bug reports, enhancement requests, and documentation issues. You do not need to write the code: identifying the problem or explaining the use case is a contribution.

Credit is a `Co-authored-by` trailer on the implementation commit, using an email associated with your GitHub account. Prefer your GitHub noreply address. Honor requests to omit attribution. Opening an issue does not guarantee that it will be implemented.

### Working with an agent

AI assistance is welcome under the same standards as other contributions. You remain responsible for understanding the change, verifying its behavior, and responding to review. Avoid generated boilerplate that obscures the problem or substitutes speculation for a reproduction.

The ideal issue is a short description of the problem and a minimal reproducible example. Do not send an unedited diagnosis, a proposed API, and several alternative fixes for a one-line bug.

## Set up the repository

Use Python 3.11, 3.12, or 3.13 and [uv](https://docs.astral.sh/uv/). Fork the repository, clone your fork, then install the package and its development group:

```bash
git clone https://github.com/YOUR-USERNAME/mcp-composer.git
cd mcp-composer/modules/mcp_composer
uv sync --group dev
```

The installable package lives in `modules/mcp_composer/` (`src/mcp_composer/`). Tests live in `modules/mcp_composer/tests/`. User-facing docs live in `docs/`. The repository root `Makefile` wraps format, lint, test, and image targets.

Copy environment defaults only when you need them:

```bash
cp .env.example .env
```

Stdio member servers fail closed unless their resolved command path is listed in `MCP_COMPOSER_STDIO_ALLOWLIST`. HTTP binds default to loopback. Non-loopback binds require authentication.

## Implement and verify

Establish what the public behavior promises before writing a regression test. Docs, protocol requirements, and maintainer decisions establish whether a difference is a bug. If the intended behavior is unclear, settle that in the issue.

Keep the change scoped to one problem and fix the causal code path. Use the surrounding code's type and exception conventions. Extend the tests nearest the behavior you change.

From `modules/mcp_composer`, run the unit suite:

```bash
uv run pytest tests/unit -q
```

Also check the code you changed:

```bash
uv run ruff check .
uv run black --check .
```

Continuous integration runs the unit suite on Python 3.11, 3.12, and 3.13. The repository still has existing ruff findings, so fix issues in the lines you touch rather than reformatting unrelated files.

From the repository root, `make test-module module=mcp_composer` runs the same unit suite. End-to-end tests under `tests/e2e/` need a running server and are not part of the default check.

Fix failures before opening the pull request. Use a new commit rather than amending a commit you have already pushed, unless a maintainer asks you to.

## Update documentation

Document new capabilities and changes to public behavior alongside the implementation. Explain the use case before the code, and keep examples runnable. Guide pages live under `docs/guide/`. The package description on PyPI is `modules/mcp_composer/PACKAGE.md`.

Preview the docs site from `docs/` with VitePress when you change navigation or a guide page.

## Submit and follow through

Write a short pull request description explaining the problem and the resulting behavior. Include the issue link. Keep "Allow edits by maintainers" enabled when available.

Review the entire diff. Green CI shows that checks passed. It does not decide whether a behavior change belongs in MCP Composer.

Read review comments, evaluate concrete findings, and respond to requested changes. Stay involved until the pull request is resolved.

## Maintainer release

Versions come from git tags matching `mcp_composer-v{version}` (see `modules/mcp_composer/pyproject.toml`).

Publishing a GitHub Release from that tag runs two workflows:

- `.github/workflows/publish.yaml` builds the wheel and attaches it to the GitHub release.
- `.github/workflows/pypi.yml` builds the same tag and publishes it to PyPI with [trusted publishing](https://docs.pypi.org/trusted-publishers/). No PyPI token is stored in the repository.

Before the first publish, add a trusted publisher on the `mcp-composer` project:

| Setting | PyPI | TestPyPI |
| --- | --- | --- |
| Owner | GitHub org that runs the workflow | same |
| Repository | `mcp-composer` | `mcp-composer` |
| Workflow | `pypi.yml` | `pypi.yml` |
| Environment | `pypi` | `testpypi` |

Create those two GitHub environments on the repository. A manual run of **Publish to PyPI** publishes to TestPyPI when "Publish to TestPyPI instead of PyPI" is checked, and only from a commit that is exactly an `mcp_composer-vX.Y.Z` tag.
