# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| Latest release and `main` | :white_check_mark: |
| Older releases | :x: |

Security fixes ship on the default branch and in the next release. Pin a current release in production.

## Reporting a Vulnerability

Report security vulnerabilities privately using [GitHub Security Advisories](https://github.com/ibm/mcp-composer/security/advisories/new).

Do not open a public issue for security concerns. Do not include exploit details in pull requests, discussions, or chat until an advisory is published.

Please include:

- A description of the issue
- Steps to reproduce, or a minimal proof of concept
- The version or commit you tested
- The impact you believe the issue has

## Scope

Reports are in scope when they show a vulnerability in MCP Composer itself: the library and server in this repository.

The following are out of scope:

- Vulnerabilities in third-party dependencies, including FastMCP and the MCP SDK. We raise version floors for known CVEs. The fix belongs upstream when the flaw is not in our code.
- Vulnerabilities in member servers, OpenAPI backends, or identity providers that MCP Composer is configured to call.
- A deployment that turns a protection off. Binding a non-loopback address without authentication, or placing an untrusted path on `MCP_COMPOSER_STDIO_ALLOWLIST`, removes that protection on purpose.

### Security boundaries

- **Network bind.** The CLI defaults to `127.0.0.1`. Serving HTTP or SSE on a non-loopback address requires authentication. A report that only shows an unauthenticated server the operator bound to `0.0.0.0` without auth is out of scope.
- **Stdio member servers.** A stdio `command` must resolve to a real path listed in `MCP_COMPOSER_STDIO_ALLOWLIST`. That allowlist is the trust boundary for local subprocesses. An empty or missing allowlist fails closed.
- **Tool visibility and catalog metadata** are routing and discovery hints. They are not access control. Authorization is the auth and policy configuration on the server.

Reports that show an enabled authentication, policy, or allowlist check failing remain in scope.

## Disclosure Process

When we receive a valid report:

1. We acknowledge the report and confirm whether it affects MCP Composer directly.
2. We develop and test a fix on a private branch.
3. We coordinate CVE assignment through GitHub's advisory process when warranted.
4. We publish the advisory and release a patched version.
5. We credit the reporter in the advisory unless they prefer otherwise.
