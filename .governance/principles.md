# Principles (OSS mcp-composer)

1. Composer is control plane, not a thin forwarder
2. Hexagonal ports/adapters — no I/O drivers in domain core
3. Fail closed on auth/policy/stdio allowlist ambiguity
4. Least privilege for tools; observe every hop
5. Generic OSS packaging (no Solis/ICR-only assumptions)
6. Public docs and samples use the Apache 2.0 community files and do not document internal hosts, registries, or SSO endpoints
