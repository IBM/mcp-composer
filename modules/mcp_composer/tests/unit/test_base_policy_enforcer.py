"""Test module for base_policy_enforcer.py"""

import pytest
from abc import ABC
from mcp_composer.middleware.acl.policy.base_policy_enforcer import BasePolicyEnforcer


class TestBasePolicyEnforcer:
    """Test cases for BasePolicyEnforcer"""

    def test_base_policy_enforcer_is_abstract(self):
        """Test that BasePolicyEnforcer is an abstract base class"""
        assert issubclass(BasePolicyEnforcer, ABC)

    def test_base_policy_enforcer_abstract_methods(self):
        """Test that BasePolicyEnforcer has required abstract methods"""
        abstract_methods = BasePolicyEnforcer.__abstractmethods__
        assert "is_allowed" in abstract_methods

    def test_cannot_instantiate_base_policy_enforcer(self):
        """Test that BasePolicyEnforcer cannot be instantiated directly"""
        with pytest.raises(TypeError):
            BasePolicyEnforcer()

    def test_concrete_implementation_required(self):
        """Test that concrete implementations must implement is_allowed"""

        class IncompletePolicyEnforcer(BasePolicyEnforcer):
            pass

        # Should raise TypeError because is_allowed is not implemented
        with pytest.raises(TypeError):
            IncompletePolicyEnforcer()

    def test_complete_concrete_implementation(self):
        """Test that a complete concrete implementation works"""

        class MockPolicyEnforcer(BasePolicyEnforcer):
            def is_allowed(self, tool_name: str, context: dict) -> bool:
                return tool_name == "allowed_tool"

        # Should work without raising TypeError
        enforcer = MockPolicyEnforcer()
        assert isinstance(enforcer, BasePolicyEnforcer)
        assert enforcer.is_allowed("allowed_tool", {}) is True
        assert enforcer.is_allowed("forbidden_tool", {}) is False

    def test_method_signature(self):
        """Test that is_allowed method has correct signature"""
        sig = BasePolicyEnforcer.is_allowed.__annotations__
        assert "tool_name" in sig
        assert sig["tool_name"] == str  # noqa: E721
        assert "context" in sig
        assert sig["context"] == dict  # noqa: E721
        assert "return" in sig
        assert sig["return"] == bool  # noqa: E721

    def test_docstring_exists(self):
        """Test that is_allowed method has docstring"""
        doc = BasePolicyEnforcer.is_allowed.__doc__
        assert doc is not None
        assert "Check if access is allowed" in doc

    def test_inheritance_chain(self):
        """Test that BasePolicyEnforcer properly inherits from ABC"""
        assert BasePolicyEnforcer.__bases__ == (ABC,)

        # Test that it's abstract
        assert hasattr(BasePolicyEnforcer, "__abstractmethods__")
        assert len(BasePolicyEnforcer.__abstractmethods__) > 0

    def test_method_abstraction(self):
        """Test that is_allowed method is properly abstract"""
        method = BasePolicyEnforcer.is_allowed
        assert hasattr(method, "__isabstractmethod__")
        assert method.__isabstractmethod__ is True

    def test_class_docstring(self):
        """Test that BasePolicyEnforcer has class docstring"""
        doc = BasePolicyEnforcer.__doc__
        assert doc is not None
        assert "Abstract base class for all policy enforcers" in doc
        assert "Implementations must define the is_allowed method" in doc

    def test_concrete_implementation_with_context(self):
        """Test concrete implementation with various context types"""

        class ContextAwarePolicyEnforcer(BasePolicyEnforcer):
            def is_allowed(self, tool_name: str, context: dict) -> bool:
                # Check user role from context
                user_role = context.get("user", {}).get("role", "user")
                if user_role == "admin":
                    return True
                elif user_role == "editor":
                    return tool_name in ["read_tool", "write_tool"]
                else:
                    return tool_name == "read_tool"

        enforcer = ContextAwarePolicyEnforcer()

        # Test with admin context
        admin_context = {"user": {"role": "admin"}}
        assert enforcer.is_allowed("any_tool", admin_context) is True

        # Test with editor context
        editor_context = {"user": {"role": "editor"}}
        assert enforcer.is_allowed("read_tool", editor_context) is True
        assert enforcer.is_allowed("write_tool", editor_context) is True
        assert enforcer.is_allowed("delete_tool", editor_context) is False

        # Test with user context
        user_context = {"user": {"role": "user"}}
        assert enforcer.is_allowed("read_tool", user_context) is True
        assert enforcer.is_allowed("write_tool", user_context) is False

        # Test with missing context
        assert enforcer.is_allowed("read_tool", {}) is True
        assert enforcer.is_allowed("write_tool", {}) is False

    def test_multiple_concrete_implementations(self):
        """Test that multiple concrete implementations work independently"""

        class AllowAllPolicyEnforcer(BasePolicyEnforcer):
            def is_allowed(self, tool_name: str, context: dict) -> bool:
                return True

        class DenyAllPolicyEnforcer(BasePolicyEnforcer):
            def is_allowed(self, tool_name: str, context: dict) -> bool:
                return False

        class SelectivePolicyEnforcer(BasePolicyEnforcer):
            def __init__(self, allowed_tools):
                self.allowed_tools = allowed_tools

            def is_allowed(self, tool_name: str, context: dict) -> bool:
                return tool_name in self.allowed_tools

        # Test different implementations
        allow_all = AllowAllPolicyEnforcer()
        deny_all = DenyAllPolicyEnforcer()
        selective = SelectivePolicyEnforcer(["tool1", "tool2"])

        context = {"user": {"role": "user"}}

        assert allow_all.is_allowed("any_tool", context) is True
        assert deny_all.is_allowed("any_tool", context) is False
        assert selective.is_allowed("tool1", context) is True
        assert selective.is_allowed("tool2", context) is True
        assert selective.is_allowed("tool3", context) is False
