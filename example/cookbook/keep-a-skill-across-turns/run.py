"""Keep a matched skill for the next turn, then add a second skill."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TURNS = (
    "how many open boxes are on the corner shelf",
    "yes go ahead",
    "seal one box",
)


def _words(text: str) -> set[str]:
    return set(text.lower().replace("-", " ").split())


def main() -> None:
    catalog = json.loads((HERE / "catalog.json").read_text(encoding="utf-8"))
    active: list[dict] = []
    for index, message in enumerate(TURNS, start=1):
        tokens = _words(message)
        for skill in catalog["skills"]:
            if skill in active:
                continue
            if tokens & set(skill["tags"]):
                active.append(skill)
        names = ", ".join(skill["name"] for skill in active)
        tools: list[str] = []
        for skill in active:
            for tool in skill["allowed-tools"]:
                if tool not in tools:
                    tools.append(tool)
        print(f"turn {index}: {names} | tools: {', '.join(tools)}")


if __name__ == "__main__":
    main()
