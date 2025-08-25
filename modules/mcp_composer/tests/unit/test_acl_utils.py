"""Test module for acl_utils.py"""

import pytest
import os
from unittest.mock import patch
from mcp_composer.middleware.acl.acl_utils import (
    resolve_role_from_context,
    extract_context_info,
    validate_policy_config
)


class TestACLUtils:
    """Test cases for ACL utilities"""

    def test_resolve_role_from_context_explicit_role(self):
        """Test resolving role from explicit role in context"""
        context = {"role": "admin"}
        role = resolve_role_from_context(context)
        assert role == "admin"

    def test_resolve_role_from_context_user_role(self):
        """Test resolving role from user object"""
        context = {"user": {"role": "editor"}}
        role = resolve_role_from_context(context)
        assert role == "editor"

    def test_resolve_role_from_context_user_roles_list(self):
        """Test resolving role from user roles list"""
        context = {"user": {"roles": ["admin", "editor"]}}
        role = resolve_role_from_context(context)
        assert role == "admin"  # Should use first role

    def test_resolve_role_from_context_jwt_claims_role(self):
        """Test resolving role from JWT claims"""
        context = {"claims": {"role": "viewer"}}
        role = resolve_role_from_context(context)
        assert role == "viewer"

    def test_resolve_role_from_context_jwt_claims_roles_list(self):
        """Test resolving role from JWT claims roles list"""
        context = {"claims": {"roles": ["user", "admin"]}}
        role = resolve_role_from_context(context)
        assert role == "user"  # Should use first role

    def test_resolve_role_from_context_headers_x_user_role(self):
        """Test resolving role from x-user-role header"""
        context = {"headers": {"x-user-role": "moderator"}}
        role = resolve_role_from_context(context)
        assert role == "moderator"

    def test_resolve_role_from_context_headers_x_role(self):
        """Test resolving role from x-role header"""
        context = {"headers": {"x-role": "superuser"}}
        role = resolve_role_from_context(context)
        assert role == "superuser"

    def test_resolve_role_from_context_priority_order(self):
        """Test that role resolution follows priority order"""
        context = {
            "role": "admin",  # Highest priority
            "user": {"role": "editor"},
            "claims": {"role": "viewer"},
            "headers": {"x-user-role": "user"}
        }
        role = resolve_role_from_context(context)
        assert role == "admin"

    def test_resolve_role_from_context_no_role_found(self):
        """Test resolving role when no role is found in context"""
        context = {"some_other_field": "value"}
        
        with patch.dict(os.environ, {"DEFAULT_USER_ROLE": "guest"}):
            role = resolve_role_from_context(context)
            assert role == "guest"

    def test_resolve_role_from_context_default_fallback(self):
        """Test resolving role with default fallback when env var not set"""
        context = {"some_other_field": "value"}
        
        with patch.dict(os.environ, {}, clear=True):
            role = resolve_role_from_context(context)
            assert role == "user"  # Default fallback

    def test_resolve_role_from_context_invalid_user_dict(self):
        """Test resolving role when user is not a dict"""
        context = {"user": "not_a_dict"}
        
        with patch.dict(os.environ, {"DEFAULT_USER_ROLE": "guest"}):
            role = resolve_role_from_context(context)
            assert role == "guest"

    def test_resolve_role_from_context_invalid_claims_dict(self):
        """Test resolving role when claims is not a dict"""
        context = {"claims": "not_a_dict"}
        
        with patch.dict(os.environ, {"DEFAULT_USER_ROLE": "guest"}):
            role = resolve_role_from_context(context)
            assert role == "guest"

    def test_resolve_role_from_context_invalid_headers_dict(self):
        """Test resolving role when headers is not a dict"""
        context = {"headers": "not_a_dict"}
        
        with patch.dict(os.environ, {"DEFAULT_USER_ROLE": "guest"}):
            role = resolve_role_from_context(context)
            assert role == "guest"

    def test_resolve_role_from_context_empty_roles_list(self):
        """Test resolving role when roles list is empty"""
        context = {"user": {"roles": []}}
        
        with patch.dict(os.environ, {"DEFAULT_USER_ROLE": "guest"}):
            role = resolve_role_from_context(context)
            assert role == "guest"

    def test_resolve_role_from_context_non_dict_context(self):
        """Test resolving role when context is not a dict"""
        context = "not_a_dict"
        
        with patch.dict(os.environ, {"DEFAULT_USER_ROLE": "guest"}):
            role = resolve_role_from_context(context)
            assert role == "guest"

    def test_extract_context_info_basic(self):
        """Test extracting basic context information"""
        context = {
            "role": "admin",
            "timestamp": "2023-01-01T00:00:00Z",
            "user": {"id": "user123"},
            "project": "test-project",
            "agent_type": "web",
            "resource_type": "tool"
        }
        
        extracted = extract_context_info(context)
        
        assert extracted["role"] == "admin"
        assert extracted["timestamp"] == "2023-01-01T00:00:00Z"
        assert extracted["user_id"] == "user123"
        assert extracted["project"] == "test-project"
        assert extracted["agent_type"] == "web"
        assert extracted["resource_type"] == "tool"

    def test_extract_context_info_from_headers(self):
        """Test extracting context information from headers"""
        context = {
            "headers": {
                "x-project": "header-project",
                "x-agent-type": "header-agent"
            }
        }
        
        extracted = extract_context_info(context)
        
        assert extracted["project"] == "header-project"
        assert extracted["agent_type"] == "header-agent"

    def test_extract_context_info_user_id_alternatives(self):
        """Test extracting user ID with alternative field names"""
        context = {"user": {"user_id": "alt_user123"}}
        
        extracted = extract_context_info(context)
        assert extracted["user_id"] == "alt_user123"

    def test_extract_context_info_missing_fields(self):
        """Test extracting context info with missing fields"""
        context = {}
        
        extracted = extract_context_info(context)
        
        assert extracted["role"] is not None  # Should have default role
        assert extracted["timestamp"] is None
        assert extracted["user_id"] is None
        assert extracted["project"] is None
        assert extracted["agent_type"] is None
        assert extracted["resource_type"] is None

    def test_extract_context_info_invalid_user_dict(self):
        """Test extracting context info when user is not a dict"""
        context = {"user": "not_a_dict"}
        
        extracted = extract_context_info(context)
        assert extracted["user_id"] is None

    def test_extract_context_info_invalid_headers_dict(self):
        """Test extracting context info when headers is not a dict"""
        context = {"headers": "not_a_dict"}
        
        extracted = extract_context_info(context)
        assert extracted["project"] is None
        assert extracted["agent_type"] is None

    def test_validate_policy_config_valid_file_mode(self):
        """Test validating policy config with valid file mode"""
        config = {"mode": "file"}
        assert validate_policy_config(config) is True

    def test_validate_policy_config_valid_vault_mode(self):
        """Test validating policy config with valid vault mode"""
        config = {"mode": "vault"}
        assert validate_policy_config(config) is True

    def test_validate_policy_config_valid_opa_mode(self):
        """Test validating policy config with valid opa mode"""
        config = {"mode": "opa"}
        assert validate_policy_config(config) is True

    def test_validate_policy_config_valid_jwt_mode(self):
        """Test validating policy config with valid jwt mode"""
        config = {"mode": "jwt"}
        assert validate_policy_config(config) is True

    def test_validate_policy_config_valid_permit_mode(self):
        """Test validating policy config with valid permit mode"""
        config = {"mode": "permit"}
        assert validate_policy_config(config) is True

    def test_validate_policy_config_missing_mode(self):
        """Test validating policy config with missing mode"""
        config = {"other_field": "value"}
        assert validate_policy_config(config) is False

    def test_validate_policy_config_invalid_mode(self):
        """Test validating policy config with invalid mode"""
        config = {"mode": "invalid_mode"}
        assert validate_policy_config(config) is False

    def test_validate_policy_config_empty_config(self):
        """Test validating empty policy config"""
        config = {}
        assert validate_policy_config(config) is False

    def test_validate_policy_config_none_config(self):
        """Test validating None policy config"""
        config = None
        assert validate_policy_config(config) is False

    def test_validate_policy_config_case_sensitive_mode(self):
        """Test that mode validation is case sensitive"""
        config = {"mode": "FILE"}  # Should be lowercase
        assert validate_policy_config(config) is False

    def test_extract_context_info_complex_nested(self):
        """Test extracting context info with complex nested structure"""
        context = {
            "user": {
                "id": "user123",
                "roles": ["admin", "editor"],
                "metadata": {"department": "engineering"}
            },
            "claims": {
                "sub": "user123",
                "roles": ["user"],
                "permissions": ["read", "write"]
            },
            "headers": {
                "authorization": "Bearer token",
                "x-project": "complex-project",
                "x-agent-type": "api-client"
            },
            "timestamp": "2023-01-01T00:00:00Z",
            "project": "direct-project",
            "agent_type": "direct-agent",
            "resource_type": "api"
        }
        
        extracted = extract_context_info(context)
        
        # Should use highest priority role (from user.roles[0])
        assert extracted["role"] == "admin"
        assert extracted["user_id"] == "user123"
        assert extracted["project"] == "direct-project"  # Direct field takes precedence
        assert extracted["agent_type"] == "direct-agent"  # Direct field takes precedence
        assert extracted["resource_type"] == "api"
        assert extracted["timestamp"] == "2023-01-01T00:00:00Z" 