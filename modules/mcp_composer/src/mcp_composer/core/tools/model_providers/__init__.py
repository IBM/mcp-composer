"""
Model Provider Adapters

This module provides adapter interfaces for different model providers (LiteLLM, Ollama, etc.).
"""

from mcp_composer.core.tools.model_providers.base import ModelProviderAdapter
from mcp_composer.core.tools.model_providers.litellm_adapter import LiteLLMAdapter
from mcp_composer.core.tools.model_providers.ollama_adapter import OllamaAdapter
from mcp_composer.core.tools.model_providers.factory import (
    ModelProviderFactory,
    DEFAULT_PROVIDER,
)

__all__ = [
    "ModelProviderAdapter",
    "LiteLLMAdapter",
    "OllamaAdapter",
    "ModelProviderFactory",
    "DEFAULT_PROVIDER",
]
