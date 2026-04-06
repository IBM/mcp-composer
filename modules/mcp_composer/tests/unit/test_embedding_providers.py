"""
Unit tests for embedding provider adapters.

Tests the new embedding functionality added to model provider adapters.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from mcp_composer.core.tools.model_providers.sentence_transformer_adapter import (
    SentenceTransformerAdapter,
)
from mcp_composer.core.tools.model_providers.litellm_adapter import LiteLLMAdapter
from mcp_composer.core.tools.model_providers.ollama_adapter import OllamaAdapter
from mcp_composer.core.tools.model_providers.factory import (
    ModelProviderFactory,
)


class TestSentenceTransformerAdapter:
    """Test SentenceTransformer embedding adapter."""

    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SENTENCE_TRANSFORMERS_AVAILABLE",
        True,
    )
    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SentenceTransformer"
    )
    def test_initialization(self, mock_st):
        """Test adapter initialization."""
        adapter = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")

        assert adapter.model_name == "all-MiniLM-L6-v2"
        mock_st.assert_called_once_with("all-MiniLM-L6-v2")

    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SENTENCE_TRANSFORMERS_AVAILABLE",
        True,
    )
    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SentenceTransformer"
    )
    def test_encode_single_text(self, mock_st):
        """Test encoding a single text string."""
        # Setup mock
        mock_model = Mock()
        mock_embedding = Mock()
        mock_embedding.tolist.return_value = [0.1, 0.2, 0.3]
        mock_model.encode.return_value = mock_embedding
        mock_st.return_value = mock_model

        adapter = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")
        result = adapter.encode("test text")

        assert result == [0.1, 0.2, 0.3]
        mock_model.encode.assert_called_once_with("test text")

    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SENTENCE_TRANSFORMERS_AVAILABLE",
        True,
    )
    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SentenceTransformer"
    )
    def test_encode_multiple_texts(self, mock_st):
        """Test encoding multiple text strings."""
        # Setup mock
        mock_model = Mock()
        mock_embeddings = [Mock(), Mock()]
        mock_embeddings[0].tolist.return_value = [0.1, 0.2, 0.3]
        mock_embeddings[1].tolist.return_value = [0.4, 0.5, 0.6]
        mock_model.encode.return_value = mock_embeddings
        mock_st.return_value = mock_model

        adapter = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")
        result = adapter.encode(["text1", "text2"])

        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_model.encode.assert_called_once_with(["text1", "text2"])

    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SENTENCE_TRANSFORMERS_AVAILABLE",
        True,
    )
    def test_is_available(self):
        """Test availability check."""
        with patch(
            "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SentenceTransformer"
        ):
            adapter = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")
            assert adapter.is_available() is True

    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SENTENCE_TRANSFORMERS_AVAILABLE",
        True,
    )
    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SentenceTransformer"
    )
    def test_get_provider_name(self, mock_st):
        """Test provider name."""
        adapter = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")
        assert adapter.get_provider_name() == "sentence-transformers"


class TestLiteLLMEmbedding:
    """Test LiteLLM embedding functionality."""

    @patch("mcp_composer.core.tools.model_providers.litellm_adapter.litellm")
    def test_encode_single_text(self, mock_litellm):
        """Test encoding a single text with LiteLLM."""
        # Setup mock response
        mock_litellm.embedding.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

        adapter = LiteLLMAdapter(base_url="http://localhost:11434")
        result = adapter.encode("test text", model_name="text-embedding-ada-002")

        assert result == [0.1, 0.2, 0.3]
        mock_litellm.embedding.assert_called_once()

    @patch("mcp_composer.core.tools.model_providers.litellm_adapter.litellm")
    def test_encode_multiple_texts(self, mock_litellm):
        """Test encoding multiple texts with LiteLLM."""
        # Setup mock response
        mock_litellm.embedding.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}]
        }

        adapter = LiteLLMAdapter(base_url="http://localhost:11434")
        result = adapter.encode(["text1", "text2"], model_name="text-embedding-ada-002")

        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    @patch("mcp_composer.core.tools.model_providers.litellm_adapter.litellm")
    def test_encode_error_handling(self, mock_litellm):
        """Test error handling in encode."""
        mock_litellm.embedding.side_effect = Exception("API Error")

        adapter = LiteLLMAdapter(base_url="http://localhost:11434")

        with pytest.raises(ValueError, match="Failed to generate embeddings"):
            adapter.encode("test text", model_name="text-embedding-ada-002")


class TestOllamaEmbedding:
    """Test Ollama embedding functionality."""

    @patch("mcp_composer.core.tools.model_providers.ollama_adapter.Client")
    @patch("mcp_composer.core.tools.model_providers.ollama_adapter.AsyncClient")
    def test_encode_single_text(self, mock_async_client, mock_client):
        """Test encoding a single text with Ollama."""
        # Setup mock
        mock_sync_client = Mock()
        mock_sync_client.embeddings.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_client.return_value = mock_sync_client

        adapter = OllamaAdapter(base_url="http://localhost:11434")
        result = adapter.encode("test text", model_name="nomic-embed-text")

        assert result == [0.1, 0.2, 0.3]
        mock_sync_client.embeddings.assert_called_once_with(
            model="nomic-embed-text", prompt="test text"
        )

    @patch("mcp_composer.core.tools.model_providers.ollama_adapter.Client")
    @patch("mcp_composer.core.tools.model_providers.ollama_adapter.AsyncClient")
    def test_encode_multiple_texts(self, mock_async_client, mock_client):
        """Test encoding multiple texts with Ollama."""
        # Setup mock
        mock_sync_client = Mock()
        mock_sync_client.embeddings.side_effect = [
            {"embedding": [0.1, 0.2, 0.3]},
            {"embedding": [0.4, 0.5, 0.6]},
        ]
        mock_client.return_value = mock_sync_client

        adapter = OllamaAdapter(base_url="http://localhost:11434")
        result = adapter.encode(["text1", "text2"], model_name="nomic-embed-text")

        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        assert mock_sync_client.embeddings.call_count == 2

    @patch("mcp_composer.core.tools.model_providers.ollama_adapter.Client")
    @patch("mcp_composer.core.tools.model_providers.ollama_adapter.AsyncClient")
    def test_encode_model_not_found(self, mock_async_client, mock_client):
        """Test error when model is not found."""
        mock_sync_client = Mock()
        mock_sync_client.embeddings.side_effect = Exception("model not found")
        mock_client.return_value = mock_sync_client

        adapter = OllamaAdapter(base_url="http://localhost:11434")

        with pytest.raises(ValueError, match="not found in Ollama"):
            adapter.encode("test text", model_name="nonexistent-model")


class TestEmbeddingProviderFactory:
    """Test embedding provider factory."""

    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SENTENCE_TRANSFORMERS_AVAILABLE",
        True,
    )
    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SentenceTransformer"
    )
    def test_create_sentence_transformer_provider(self, mock_st):
        """Test creating sentence-transformers provider."""
        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="sentence-transformers", model_name="all-MiniLM-L6-v2"
        )

        assert adapter is not None
        assert adapter.model_name == "all-MiniLM-L6-v2"
        mock_st.assert_called_once_with("all-MiniLM-L6-v2")

    @patch("mcp_composer.core.tools.model_providers.factory.LiteLLMAdapter")
    def test_create_litellm_provider(self, mock_adapter):
        """Test creating litellm provider."""
        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="litellm",
            model_name="text-embedding-ada-002",
            base_url="http://localhost:11434",
        )

        mock_adapter.assert_called_once_with(base_url="http://localhost:11434")

    @patch("mcp_composer.core.tools.model_providers.factory.LiteLLMAdapter")
    @patch.dict("os.environ", {}, clear=True)
    def test_create_litellm_openai_provider(self, mock_adapter):
        """Test creating LiteLLM provider with OpenAI configuration."""
        import os

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="litellm",
            model_provider="openai",
            model_name="text-embedding-ada-002",
            api_key="sk-test-key",
        )

        # Verify API key was set
        assert os.environ.get("OPENAI_API_KEY") == "sk-test-key"
        # Verify model was stored
        assert mock_instance._embedding_model == "text-embedding-ada-002"

    @patch("mcp_composer.core.tools.model_providers.factory.LiteLLMAdapter")
    @patch.dict("os.environ", {}, clear=True)
    def test_create_litellm_gemini_provider(self, mock_adapter):
        """Test creating LiteLLM provider with Google Gemini configuration."""
        import os

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="litellm",
            model_provider="gemini",
            model_name="gemini/text-embedding-004",
            api_key="AIza-test-key",
        )

        # Verify API key was set
        assert os.environ.get("GEMINI_API_KEY") == "AIza-test-key"
        # Verify model was stored
        assert mock_instance._embedding_model == "gemini/text-embedding-004"

    @patch("mcp_composer.core.tools.model_providers.factory.LiteLLMAdapter")
    @patch.dict("os.environ", {}, clear=True)
    def test_create_litellm_azure_provider(self, mock_adapter):
        """Test creating LiteLLM provider with Azure OpenAI configuration."""
        import os

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="litellm",
            model_provider="azure",
            model_name="azure/text-embedding-ada-002",
            api_key="azure-test-key",
            base_url="https://test.openai.azure.com",
        )

        # Verify API key was set
        assert os.environ.get("AZURE_API_KEY") == "azure-test-key"
        # Verify model was stored
        assert mock_instance._embedding_model == "azure/text-embedding-ada-002"

    @patch("mcp_composer.core.tools.model_providers.factory.LiteLLMAdapter")
    @patch.dict("os.environ", {}, clear=True)
    def test_create_litellm_cohere_provider(self, mock_adapter):
        """Test creating LiteLLM provider with Cohere configuration."""
        import os

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="litellm",
            model_provider="cohere",
            model_name="cohere/embed-english-v3.0",
            api_key="cohere-test-key",
        )

        # Verify API key was set
        assert os.environ.get("COHERE_API_KEY") == "cohere-test-key"
        # Verify model was stored
        assert mock_instance._embedding_model == "cohere/embed-english-v3.0"

    @patch("mcp_composer.core.tools.model_providers.factory.LiteLLMAdapter")
    @patch.dict("os.environ", {}, clear=True)
    def test_create_litellm_infer_from_model_name_gemini(self, mock_adapter):
        """Test inferring Gemini provider from model name."""
        import os

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="litellm",
            model_name="gemini/text-embedding-004",
            api_key="AIza-test-key",
        )

        # Verify API key was set for Gemini
        assert os.environ.get("GEMINI_API_KEY") == "AIza-test-key"
        assert mock_instance._embedding_model == "gemini/text-embedding-004"

    @patch("mcp_composer.core.tools.model_providers.factory.LiteLLMAdapter")
    @patch.dict("os.environ", {}, clear=True)
    def test_create_litellm_infer_from_model_name_azure(self, mock_adapter):
        """Test inferring Azure provider from model name."""
        import os

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="litellm",
            model_name="azure/text-embedding-ada-002",
            api_key="azure-test-key",
        )

        # Verify API key was set for Azure
        assert os.environ.get("AZURE_API_KEY") == "azure-test-key"
        assert mock_instance._embedding_model == "azure/text-embedding-ada-002"

    @patch("mcp_composer.core.tools.model_providers.factory.LiteLLMAdapter")
    @patch.dict("os.environ", {}, clear=True)
    def test_create_litellm_default_to_openai(self, mock_adapter):
        """Test defaulting to OpenAI when no provider specified."""
        import os

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="litellm",
            model_name="text-embedding-ada-002",
            api_key="sk-test-key",
        )

        # Verify API key was set for OpenAI (default)
        assert os.environ.get("OPENAI_API_KEY") == "sk-test-key"
        assert mock_instance._embedding_model == "text-embedding-ada-002"

    @patch("mcp_composer.core.tools.model_providers.factory.LiteLLMAdapter")
    @patch.dict("os.environ", {}, clear=True)
    def test_create_litellm_with_default_model_openai(self, mock_adapter):
        """Test using default model for OpenAI."""
        import os

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="litellm", model_provider="openai", api_key="sk-test-key"
        )

        # Verify default OpenAI model was used
        assert mock_instance._embedding_model == "text-embedding-ada-002"

    @patch("mcp_composer.core.tools.model_providers.factory.LiteLLMAdapter")
    @patch.dict("os.environ", {}, clear=True)
    def test_create_litellm_with_default_model_gemini(self, mock_adapter):
        """Test using default model for Gemini."""
        import os

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="litellm", model_provider="gemini", api_key="AIza-test-key"
        )

        # Verify default Gemini model was used
        assert mock_instance._embedding_model == "gemini/gemini-embedding-001"

    @patch("mcp_composer.core.tools.model_providers.factory.OllamaAdapter")
    def test_create_ollama_provider(self, mock_adapter):
        """Test creating ollama provider."""
        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="ollama",
            model_name="nomic-embed-text",
            base_url="http://localhost:11434",
        )

        mock_adapter.assert_called_once_with(base_url="http://localhost:11434")

    def test_create_invalid_provider(self):
        """Test error with invalid provider name."""
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            ModelProviderFactory.create_embedding_provider(
                provider_name="invalid-provider"
            )

    def test_get_default_provider(self):
        """Test getting default provider."""
        assert (
            ModelProviderFactory.get_default_embedding_provider()
            == "sentence-transformers"
        )

    def test_get_available_providers(self):
        """Test getting available providers."""
        providers = ModelProviderFactory.get_available_embedding_providers()
        assert "sentence-transformers" in providers
        assert "litellm" in providers
        assert "ollama" in providers

    def test_unsupported_model_provider_warning(self):
        """Test that unsupported model_provider still creates adapter."""
        # Even with unsupported provider, adapter should be created
        # (warning is logged but doesn't prevent creation)
        adapter = ModelProviderFactory.create_embedding_provider(
            provider_name="litellm",
            model_provider="unsupported_provider",
            api_key="test-key",
        )

        # Should still create adapter despite unsupported provider
        assert adapter is not None
        # API key should be set as LITELLM_API_KEY for unsupported providers
        import os

        assert os.environ.get("LITELLM_API_KEY") == "test-key"

    def test_supported_model_providers_validation(self):
        """Test that all supported providers are validated correctly."""
        from mcp_composer.core.tools.model_providers.factory import (
            SUPPORTED_LITELLM_PROVIDERS,
        )

        # Verify the constant exists and contains expected providers
        assert "openai" in SUPPORTED_LITELLM_PROVIDERS
        assert "gemini" in SUPPORTED_LITELLM_PROVIDERS
        assert "google" in SUPPORTED_LITELLM_PROVIDERS
        assert "azure" in SUPPORTED_LITELLM_PROVIDERS
        assert "cohere" in SUPPORTED_LITELLM_PROVIDERS
        assert "anthropic" in SUPPORTED_LITELLM_PROVIDERS
        assert "huggingface" in SUPPORTED_LITELLM_PROVIDERS

    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SENTENCE_TRANSFORMERS_AVAILABLE",
        True,
    )
    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SentenceTransformer"
    )
    def test_is_provider_available(self, mock_st):
        """Test checking provider availability."""
        assert (
            ModelProviderFactory.is_embedding_provider_available(
                "sentence-transformers"
            )
            is True
        )


class TestA2AEmbeddingIntegration:
    """Test A2A service embedding integration."""

    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SENTENCE_TRANSFORMERS_AVAILABLE",
        True,
    )
    @patch(
        "mcp_composer.core.tools.model_providers.sentence_transformer_adapter.SentenceTransformer"
    )
    def test_generate_embeddings_with_text(self, mock_st):
        """Test generating embeddings with valid text."""
        from mcp_composer.a2a_service.a2a_mcp import generate_embeddings

        # Setup mock for SentenceTransformer
        mock_model = Mock()
        mock_embedding = Mock()
        mock_embedding.tolist.return_value = [0.1, 0.2, 0.3]
        mock_model.encode.return_value = mock_embedding
        mock_st.return_value = mock_model

        # Reset global adapter
        import mcp_composer.a2a_service.a2a_mcp as a2a_module

        a2a_module._embedding_adapter = None

        result = generate_embeddings("test text")
        assert result == [0.1, 0.2, 0.3]

    def test_generate_embeddings_with_empty_text(self):
        """Test generating embeddings with empty text."""
        from mcp_composer.a2a_service.a2a_mcp import generate_embeddings

        result = generate_embeddings("")
        assert result == []

    def test_generate_embeddings_with_none(self):
        """Test generating embeddings with None."""
        from mcp_composer.a2a_service.a2a_mcp import generate_embeddings

        result = generate_embeddings(None)
        assert result == []
