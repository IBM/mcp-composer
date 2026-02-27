#!/usr/bin/env python3
"""
Simple test script to verify Vault connection and authentication.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from mcp_composer.middleware.acl.policy.vault_enforcer import (
    HashiCorpVaultPolicyEnforcer,
)


def test_vault_connection():
    """Test Vault connection with the same parameters as the test."""

    print("Testing Vault connection...")

    # Same parameters as in test_policy.py
    vault_url = "http://127.0.0.1:8200"
    vault_token = "root"

    print(f"Vault URL: {vault_url}")
    print(f"Vault Token: {vault_token}")

    try:
        # Test direct hvac connection first
        import hvac

        print("✓ hvac library is available")

        client = hvac.Client(url=vault_url, token=vault_token)
        print("✓ Created hvac client")

        # Test authentication
        if client.is_authenticated():
            print("✓ Vault client is authenticated")

            # Test reading a simple secret
            try:
                # Try to read a test secret
                client.secrets.kv.v2.read_secret_version(
                    path="test", mount_point="secret"
                )
                print("✓ Successfully read from Vault KV store")
            except Exception as e:
                if "InvalidPath" in str(e):
                    print(
                        "✓ Vault KV store is accessible (test path doesn't exist, which is expected)"
                    )
                else:
                    print(f"⚠ Error reading from Vault: {e}")
        else:
            print("✗ Vault client is NOT authenticated")
            print("  This could be due to:")
            print("  - Invalid token")
            print("  - Vault server not running")
            print("  - Network connectivity issues")

    except ImportError:
        print("✗ hvac library not installed. Install with: pip install hvac")
        return False
    except Exception as e:
        print(f"✗ Error creating Vault client: {e}")
        return False

    # Now test the enforcer
    print("\nTesting HashiCorpVaultPolicyEnforcer...")

    try:
        enforcer = HashiCorpVaultPolicyEnforcer(
            vault_url=vault_url,
            token=vault_token,
            mount_point="secret",
            policy_path="mcp-policies",
        )

        if enforcer.client and enforcer.client.is_authenticated():
            print("✓ HashiCorpVaultPolicyEnforcer initialized successfully")

            # Test policy retrieval
            test_role = "admin"
            policy = enforcer._get_policy_from_vault(test_role)
            if policy:
                print(f"✓ Found policy for role '{test_role}': {policy}")
            else:
                print(
                    f"⚠ No policy found for role '{test_role}' (this is expected if no policies are set up)"
                )

        else:
            print("✗ HashiCorpVaultPolicyEnforcer failed to authenticate")
            return False

    except Exception as e:
        print(f"✗ Error initializing HashiCorpVaultPolicyEnforcer: {e}")
        return False

    print("\n✓ Vault connection test completed successfully!")
    return True


if __name__ == "__main__":
    success = test_vault_connection()
    sys.exit(0 if success else 1)
