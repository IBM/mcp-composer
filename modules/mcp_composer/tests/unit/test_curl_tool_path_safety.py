"""Tool ids must not escape the custom_tool output directory."""

from pathlib import Path

import pytest

from mcp_composer.core.utils import custom_tool
from mcp_composer.core.utils.custom_tool import (
    DynamicToolGenerator,
    OpenApiTool,
    safe_child_path,
)

BAD_IDS = [
    "../../../../tmp/pwned",
    "../x",
    "..",
    ".",
    "/etc/cron.d/pwn",
    "a/b",
    "a\\b",
    "bad\x00id",
    "",
]


@pytest.mark.parametrize("bad", BAD_IDS)
def test_safe_child_path_rejects_escapes(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        safe_child_path(tmp_path, bad)


def test_safe_child_path_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "link").symlink_to(outside)
    with pytest.raises(ValueError):
        safe_child_path(root, "link")


def test_safe_child_path_accepts_plain_name(tmp_path: Path) -> None:
    assert safe_child_path(tmp_path, "my-tool") == (tmp_path / "my-tool").resolve()


@pytest.mark.parametrize("bad", [b for b in BAD_IDS if b])
def test_write_curl_to_file_rejects_malicious_id(
    bad: str, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(custom_tool.ToolPaths, "OUTPUT_DIR_NAME", str(tmp_path))
    with pytest.raises(ValueError):
        DynamicToolGenerator.write_curl_to_file({"id": bad})
    assert list(tmp_path.rglob("*")) == []


def test_write_curl_to_file_rejects_missing_id() -> None:
    with pytest.raises(ValueError):
        DynamicToolGenerator.write_curl_to_file({})


def test_write_curl_to_file_writes_inside_root(monkeypatch, tmp_path: Path) -> None:
    # An absolute OUTPUT_DIR_NAME replaces the package dir in the path join.
    monkeypatch.setattr(custom_tool.ToolPaths, "OUTPUT_DIR_NAME", str(tmp_path))
    DynamicToolGenerator.write_curl_to_file({"id": "ok-tool", "x": 1})
    written = list(tmp_path.rglob("tools.json"))
    assert len(written) == 1
    assert "ok-tool" in written[0].parts


@pytest.mark.parametrize("bad", ["../evil", "/abs/evil", "a/b"])
def test_openapi_tool_rejects_malicious_name(bad: str) -> None:
    with pytest.raises(ValueError):
        OpenApiTool(bad, {}, None)
