import pytest
from mcp_composer.core.utils import exceptions


def test_mcpcomposererror_inheritance():
    err = exceptions.MCPComposerError("base error")
    assert isinstance(err, Exception)
    assert isinstance(err, exceptions.MCPComposerError)
    assert str(err) == "base error"


def test_toolduplicateerror_inheritance():
    err = exceptions.ToolDuplicateError("duplicate")
    assert isinstance(err, exceptions.MCPComposerError)
    assert isinstance(err, exceptions.ToolDuplicateError)
    assert str(err) == "duplicate"


def test_toolfiltererror_inheritance():
    err = exceptions.ToolFilterError("filter")
    assert isinstance(err, exceptions.MCPComposerError)
    assert isinstance(err, exceptions.ToolFilterError)
    assert str(err) == "filter"


def test_toolgenerateerror_inheritance():
    err = exceptions.ToolGenerateError("generate")
    assert isinstance(err, exceptions.MCPComposerError)
    assert isinstance(err, exceptions.ToolGenerateError)
    assert str(err) == "generate"


def test_tooldisableerror_inheritance():
    err = exceptions.ToolDisableError("disable")
    assert isinstance(err, exceptions.MCPComposerError)
    assert isinstance(err, exceptions.ToolDisableError)
    assert str(err) == "disable"


def test_memberservererror_inheritance():
    err = exceptions.MemberServerError("member")
    assert isinstance(err, exceptions.MCPComposerError)
    assert isinstance(err, exceptions.MemberServerError)
    assert str(err) == "member"


@pytest.mark.parametrize(
    "exc_cls",
    [
        exceptions.ToolDuplicateError,
        exceptions.ToolFilterError,
        exceptions.ToolGenerateError,
        exceptions.ToolDisableError,
        exceptions.MemberServerError,
    ],
)
def test_raises_custom_exceptions(exc_cls):
    with pytest.raises(exc_cls):
        raise exc_cls("error message")
