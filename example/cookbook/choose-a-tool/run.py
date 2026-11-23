"""Pick a small toolset for a request, or ask when two tools still match."""

import re

TOOLS = (
    {
        "name": "count_open_boxes",
        "words": frozenset({"count", "open", "boxes"}),
        "effect": "read",
    },
    {
        "name": "count_sealed_boxes",
        "words": frozenset({"count", "sealed", "boxes"}),
        "effect": "read",
    },
    {
        "name": "seal_box",
        "words": frozenset({"seal", "box"}),
        "effect": "write",
    },
)

REQUESTS = (
    "count the open boxes",
    "count the boxes",
    "seal boxes",
    "seal one box",
    "what is the weather",
)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def choose(request: str) -> str:
    """Return RESOLVED, FAN_OUT, CLARIFY, or NO_MATCH plus the tool names."""
    tokens = _tokens(request)
    scored = sorted(
        ((len(tool["words"] & tokens), tool["name"], tool["effect"]) for tool in TOOLS),
        key=lambda item: (-item[0], item[1]),
    )
    best, second = scored[0], scored[1]
    if best[0] == 0:
        return "NO_MATCH"
    if best[0] == second[0]:
        tied = [item for item in scored if item[0] == best[0]]
        names = ", ".join(sorted(item[1] for item in tied))
        if any(item[2] == "write" for item in tied):
            return f"CLARIFY {names}"
        return f"FAN_OUT {names}"
    return f"RESOLVED {best[1]}"


def main() -> None:
    for request in REQUESTS:
        print(f"{request}: {choose(request)}")


if __name__ == "__main__":
    main()
