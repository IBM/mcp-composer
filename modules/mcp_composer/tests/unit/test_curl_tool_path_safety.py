"""ToolBuilderConfig must reject path-like tool names."""

import pytest

from mcp_composer.core.models.tool import ToolBuilderConfig

BAD_NAMES = [
    "../../../../tmp/pwned",
    "../x",
    "..",
    ".",
    "/etc/cron.d/pwn",
    "a/b",
    "a\\b",
    "bad\x00id",
    " ",
    "..\\x",
]


@pytest.mark.parametrize("bad", BAD_NAMES)
def test_tool_builder_config_rejects_path_like_name(bad: str) -> None:
    with pytest.raises(ValueError):
        ToolBuilderConfig(
            name=bad,
            tool_type="curl",
            description="d",
            curl_config={"value": "curl https://example.com"},
        )


def test_tool_builder_config_accepts_plain_name() -> None:
    cfg = ToolBuilderConfig(
        name="Customer API",
        tool_type="curl",
        description="d",
        curl_config={"value": "curl https://example.com"},
    )
    assert cfg.name == "Customer API"
