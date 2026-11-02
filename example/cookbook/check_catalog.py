"""Fail when a catalog entry has no page, no runner, or a forbidden word."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "docs" / "cookbook" / "catalog.json"
FORBIDDEN = ("ibm", "solis", "mosaic", "mosaci")


def main() -> int:
    recipes = json.loads(CATALOG.read_text(encoding="utf-8"))
    errors: list[str] = []
    seen: set[str] = set()
    for recipe in recipes:
        slug = recipe["slug"]
        if slug in seen:
            errors.append(f"duplicate slug {slug}")
        seen.add(slug)
        folder = ROOT / "example" / "cookbook" / slug
        page = ROOT / "docs" / "cookbook" / f"{slug}.md"
        runner = folder / "run.py"
        if not page.is_file():
            errors.append(f"missing page {page.relative_to(ROOT)}")
        if not runner.is_file():
            errors.append(f"missing runner {runner.relative_to(ROOT)}")
        paths = [page]
        if folder.is_dir():
            paths.extend(path for path in folder.rglob("*") if path.is_file())
        for path in paths:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8").lower()
            for word in FORBIDDEN:
                if word in text:
                    errors.append(f"{path.relative_to(ROOT)} contains {word}")
    index = (
        (ROOT / "docs" / "cookbook" / "index.md").read_text(encoding="utf-8").lower()
    )
    for word in FORBIDDEN:
        if word in index:
            errors.append(f"docs/cookbook/index.md contains {word}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"catalog ok: {len(recipes)} recipes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
