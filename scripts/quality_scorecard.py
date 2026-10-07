#!/usr/bin/env python3
"""Local Sonar-style quality scorecard (no SonarQube required)."""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "modules" / "mcp_composer"
SRC = MODULE / "src"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def bandit_summary() -> dict:
    out = MODULE / ".quality_bandit.json"
    proc = run(
        ["uv", "run", "bandit", "-r", "src", "-f", "json", "-o", str(out), "-q"],
        MODULE,
    )
    if not out.exists():
        return {"error": proc.stderr[-400:] or proc.stdout[-400:] or "bandit failed"}
    data = json.loads(out.read_text())
    results = data.get("results", [])
    by_sev = Counter(r["issue_severity"] for r in results)
    high = [
        f"{r['test_id']} {r['filename'].replace('src/mcp_composer/', '')}:{r['line_number']} — {r['issue_text']}"
        for r in results
        if r["issue_severity"] == "HIGH"
    ]
    med_codes = Counter(r["test_id"] for r in results if r["issue_severity"] == "MEDIUM")
    return {
        "high": by_sev.get("HIGH", 0),
        "medium": by_sev.get("MEDIUM", 0),
        "low": by_sev.get("LOW", 0),
        "high_items": high,
        "medium_codes": med_codes.most_common(8),
        "loc": data.get("metrics", {}).get("_totals", {}).get("loc", "?"),
    }


def ruff_summary() -> dict:
    proc = run(["uv", "run", "ruff", "check", ".", "--output-format=json"], MODULE)
    if proc.returncode not in (0, 1):
        return {"error": proc.stderr[-300:] or "ruff failed"}
    try:
        issues = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return {"error": "ruff json parse failed"}
    return {"count": len(issues), "by_code": Counter(i.get("code") for i in issues).most_common(8)}


def main() -> int:
    print("=== Local quality scorecard (Sonar-style, no SonarQube) ===\n")
    print("Mapping:")
    print("  Reliability/Bugs+Security  -> bandit HIGH/MEDIUM")
    print("  Maintainability/Code smells -> ruff (+ pylint optional)")
    print("  Coverage gate               -> make coverage (fail_under=85)\n")

    bandit = bandit_summary()
    ruff = ruff_summary()

    if "error" in bandit:
        print("Bandit: ERROR", bandit["error"])
    else:
        print(f"Security/Bugs (bandit)  HIGH={bandit['high']}  MEDIUM={bandit['medium']}  LOW={bandit['low']}  LOC={bandit['loc']}")
        if bandit["high_items"]:
            print("  HIGH findings:")
            for item in bandit["high_items"]:
                print(f"    - {item}")
        if bandit["medium_codes"]:
            print("  MEDIUM by rule:")
            for code, n in bandit["medium_codes"]:
                print(f"    - {code}: {n}")

    if "error" in ruff:
        print("Ruff: ERROR", ruff["error"])
    else:
        print(f"\nCode smells (ruff)      count={ruff['count']}")
        if ruff["by_code"]:
            for code, n in ruff["by_code"]:
                print(f"    - {code}: {n}")
        else:
            print("    (clean)")

    # Gate: fail on HIGH security like a Sonar quality gate
    high = bandit.get("high", 0) if "error" not in bandit else 0
    ruff_n = ruff.get("count", 0) if "error" not in ruff else 0
    print("\nQuality gate (local):")
    print(f"  bandit HIGH == 0: {'PASS' if high == 0 else 'FAIL'}")
    print(f"  ruff errors == 0: {'PASS' if ruff_n == 0 else 'FAIL'}")
    print("  coverage >= 85%:  run `make coverage` / module pytest-cov")
    return 1 if high or ruff_n else 0


if __name__ == "__main__":
    sys.exit(main())
