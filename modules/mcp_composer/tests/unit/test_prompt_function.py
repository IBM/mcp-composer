"""Prompt templates stay data. They are not compiled or executed."""

from __future__ import annotations

import pytest

from mcp_composer.core.utils.utils import (
    _create_prompt_function,
    build_prompt_from_dict,
)


def test_template_text_is_not_executed() -> None:
    template = '"""; raise RuntimeError("executed")\ndef _ignored(): #'
    prompt = build_prompt_from_dict(
        {
            "name": "literal-template",
            "template": template,
            "arguments": [{"name": "x"}],
        }
    )
    rendered = prompt.fn(x="ok")
    assert "raise RuntimeError" in rendered
    assert "executed" in rendered


def test_named_argument_is_substituted() -> None:
    fn = _create_prompt_function("Hello {name}", [{"name": "name"}])
    assert fn(name="Ada") == "Hello Ada"


def test_doubled_braces_stay_literal() -> None:
    fn = _create_prompt_function("Show '{{ application }}'", [{"name": "application"}])
    assert fn(application="billing") == "Show '{ application }'"


def test_attribute_access_in_template_is_rejected() -> None:
    fn = _create_prompt_function("{name.__class__}", [{"name": "name"}])
    with pytest.raises(ValueError, match="undefined argument"):
        fn(name="Ada")


def test_argument_name_must_be_an_identifier() -> None:
    with pytest.raises(ValueError, match="Invalid prompt argument name"):
        _create_prompt_function("x", [{"name": "os.system"}])
