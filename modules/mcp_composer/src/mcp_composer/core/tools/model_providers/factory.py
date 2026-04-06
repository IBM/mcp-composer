"""
Model Provider Factory

Factory for creating model provider adapters based on configuration.
Supports both chat/completion and embedding generation.
"""

from typing import Dict, Any, Optional
from mcp_composer.core.tools.model_providers.base import ModelProviderAdapter
from mcp_composer.core.tools.model_providers.litellm_adapter import LiteLLMAdapter
from mcp_composer.core.tools.model_providers.ollama_adapter import OllamaAdapter
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

# Provider registry for chat/completion
PROVIDER_REGISTRY: Dict[str, type[ModelProviderAdapter]] = {
    "litellm": LiteLLMAdapter,
    "ollama": OllamaAdapter,
}

# Default provider for chat
DEFAULT_PROVIDER = "litellm"

# Default provider for embeddings
DEFAULT_EMBEDDING_PROVIDER = "sentence-transformers"

# Supported model providers for LiteLLM
SUPPORTED_LITELLM_PROVIDERS = {
    "openai",
    "gemini",
    "google",
    "azure",
    "cohere",
    "anthropic",
    "huggingface",
}


class ModelProviderFactory:
    """
    Factory for creating model provider adapters.
    """

    @staticmethod
    def create_provider(
        provider_name: str = DEFAULT_PROVIDER, base_url: str = "http://localhost:11434"
    ) -> ModelProviderAdapter:
        """
        Create a model provider adapter.

        Args:
            provider_name: Name of the provider ("litellm" or "ollama")
            base_url: Base URL for the model API

        Returns:
            ModelProviderAdapter instance

        Raises:
            ValueError: If the provider is not supported
            ImportError: If the provider library is not available
        """
        provider_name = provider_name.lower()

        if provider_name not in PROVIDER_REGISTRY:
            available = ", ".join(PROVIDER_REGISTRY.keys())
            raise ValueError(
                f"Unsupported provider '{provider_name}'. "
                f"Available providers: {available}"
            )

        adapter_class = PROVIDER_REGISTRY[provider_name]

        try:
            adapter = adapter_class(base_url=base_url)
            logger.info("Created %s adapter with base_url=%s", provider_name, base_url)
            return adapter
        except ImportError as e:
            logger.error("Failed to create %s adapter: %s", provider_name, e)
            raise

    @staticmethod
    def get_default_provider() -> str:
        """Get the default provider name."""
        return DEFAULT_PROVIDER

    @staticmethod
    def get_available_providers() -> list[str]:
        """Get list of available provider names."""
        return list(PROVIDER_REGISTRY.keys())

    @staticmethod
    def is_provider_available(provider_name: str) -> bool:
        """
        Check if a provider is available (library installed).

        Args:
            provider_name: Name of the provider to check

        Returns:
            True if the provider is available, False otherwise
        """
        provider_name = provider_name.lower()

        if provider_name not in PROVIDER_REGISTRY:
            return False

        adapter_class = PROVIDER_REGISTRY[provider_name]

        # Try to create an instance to check availability
        try:
            adapter = adapter_class(base_url="http://localhost:11434")
            return adapter.is_available()
        except Exception:
            return False

    @staticmethod
    def create_embedding_provider(
        provider_name: str = DEFAULT_EMBEDDING_PROVIDER,
        model_name: Optional[str] = None,
        model_provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> ModelProviderAdapter:
        """
        Create a model provider adapter for embedding generation.

        Args:
            provider_name: Name of the provider ("sentence-transformers", "litellm", or "ollama")
            model_name: Name of the model to use (stored for later use with encode())
            model_provider: For LiteLLM, the underlying provider (e.g., "openai", "gemini", "azure")
            api_key: API key for the provider (if required, e.g., for LiteLLM)
            base_url: Base URL for the API (if required, e.g., for Ollama)

        Returns:
            ModelProviderAdapter instance with embedding support

        Raises:
            ValueError: If the provider is not supported
            ImportError: If the provider library is not available
        """
        provider_name = provider_name.lower()

        try:
            # Create adapter with appropriate parameters based on provider
            if provider_name == "sentence-transformers":
                from mcp_composer.core.tools.model_providers.sentence_transformer_adapter import (
                    SentenceTransformerAdapter,
                )

                # Default embedding model constant
                DEFAULT_SENTENCE_TRANSFORMER_MODEL = "all-MiniLM-L6-v2"
                model_name = model_name or DEFAULT_SENTENCE_TRANSFORMER_MODEL
                adapter = SentenceTransformerAdapter(model_name=model_name)
            elif provider_name == "litellm":
                import os

                base_url = base_url or "http://localhost:11434"
                adapter = LiteLLMAdapter(base_url=base_url)

                # Determine the model provider and set appropriate defaults
                if model_provider:
                    model_provider = model_provider.lower()

                    # Validate model_provider against supported providers
                    if model_provider not in SUPPORTED_LITELLM_PROVIDERS:
                        logger.warning(
                            "Unsupported model_provider '%s'. Supported providers: %s. "
                            "API key will be set as LITELLM_API_KEY.",
                            model_provider,
                            ", ".join(sorted(SUPPORTED_LITELLM_PROVIDERS)),
                        )

                    # Set API key based on provider
                    if api_key:
                        if model_provider == "openai":
                            os.environ["OPENAI_API_KEY"] = api_key
                            model_name = model_name or "text-embedding-ada-002"
                        elif model_provider in ["gemini", "google"]:
                            os.environ["GEMINI_API_KEY"] = api_key
                            model_name = model_name or "gemini/gemini-embedding-001"
                        elif model_provider == "azure":
                            os.environ["AZURE_API_KEY"] = api_key
                            model_name = model_name or "azure/text-embedding-3-large"
                        elif model_provider == "cohere":
                            os.environ["COHERE_API_KEY"] = api_key
                            model_name = model_name or "cohere/embed-english-v3.0"
                        elif model_provider == "anthropic":
                            os.environ["ANTHROPIC_API_KEY"] = api_key
                            model_name = (
                                model_name or "anthropic/claude-3-opus-20240229"
                            )
                        elif model_provider == "huggingface":
                            os.environ["HUGGINGFACE_API_KEY"] = api_key
                            model_name = (
                                model_name
                                or "huggingface/sentence-transformers/all-MiniLM-L6-v2"
                            )
                        else:
                            # Generic/unsupported provider - set as LITELLM_API_KEY
                            os.environ["LITELLM_API_KEY"] = api_key
                else:
                    # No model_provider specified, try to infer from model_name or use default
                    if api_key:
                        if model_name and model_name.startswith("gemini/"):
                            os.environ["GEMINI_API_KEY"] = api_key
                        elif model_name and model_name.startswith("azure/"):
                            os.environ["AZURE_API_KEY"] = api_key
                        elif model_name and model_name.startswith("cohere/"):
                            os.environ["COHERE_API_KEY"] = api_key
                        else:
                            # Default to OpenAI
                            os.environ["OPENAI_API_KEY"] = api_key

                    model_name = model_name or "text-embedding-ada-002"

                # Store model name for later use
                adapter._embedding_model = model_name

                logger.info(
                    "Configured LiteLLM embedding adapter: provider=%s, model=%s",
                    model_provider or "inferred",
                    model_name,
                )
            elif provider_name == "ollama":
                base_url = base_url or "http://localhost:11434"
                adapter = OllamaAdapter(base_url=base_url)
                # Store model name for later use
                adapter._embedding_model = model_name or "nomic-embed-text"
            else:
                available = ["sentence-transformers", "litellm", "ollama"]
                raise ValueError(
                    f"Unsupported embedding provider '{provider_name}'. "
                    f"Available providers: {', '.join(available)}"
                )

            logger.info(
                "Created %s embedding adapter with model=%s",
                provider_name,
                model_name or "default",
            )
            return adapter
        except ImportError as e:
            logger.error("Failed to create %s embedding adapter: %s", provider_name, e)
            raise

    @staticmethod
    def get_default_embedding_provider() -> str:
        """Get the default embedding provider name."""
        return DEFAULT_EMBEDDING_PROVIDER

    @staticmethod
    def get_available_embedding_providers() -> list[str]:
        """Get list of available embedding provider names."""
        return ["sentence-transformers", "litellm", "ollama"]

    @staticmethod
    def is_embedding_provider_available(provider_name: str) -> bool:
        """
        Check if an embedding provider is available (library installed).

        Args:
            provider_name: Name of the provider to check

        Returns:
            True if the provider is available, False otherwise
        """
        provider_name = provider_name.lower()

        # Try to create an instance to check availability
        try:
            if provider_name == "sentence-transformers":
                from mcp_composer.core.tools.model_providers.sentence_transformer_adapter import (
                    SentenceTransformerAdapter,
                )

                adapter = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")
            elif provider_name == "litellm":
                adapter = LiteLLMAdapter(base_url="http://localhost:11434")
            elif provider_name == "ollama":
                adapter = OllamaAdapter(base_url="http://localhost:11434")
            else:
                return False
            return adapter.is_available()
        except Exception:
            return False
