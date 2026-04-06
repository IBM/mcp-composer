"""
Base Model Provider Adapter

Abstract base class for model provider adapters.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union


class ModelProviderAdapter(ABC):
    """
    Abstract base class for model provider adapters.

    This defines the interface that all model providers must implement.
    Supports both chat/completion and embedding generation.
    """

    _embedding_model: Optional[str] = None

    @abstractmethod
    async def chat(
        self,
        model_name: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        options: Dict[str, Any] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Send a chat request to the model provider.

        Args:
            model_name: Name of the model to use
            prompt: The prompt text to send
            temperature: Generation temperature (0.0-2.0)
            max_tokens: Maximum number of tokens to generate
            options: Additional provider-specific options
            **kwargs: Additional provider-specific parameters

        Returns:
            Dictionary containing:
                - response: The model's response text
                - usage: Dictionary with token usage information (optional)
                    - prompt_tokens: Number of tokens in prompt
                    - completion_tokens: Number of tokens in completion
                    - total_tokens: Total tokens used

        Raises:
            ImportError: If the provider library is not available
            ValueError: If the request fails
        """
        pass

    def encode(
        self, text: Union[str, List[str]], model_name: str = None, **kwargs
    ) -> Union[List[float], List[List[float]]]:
        """
        Generate embeddings for the given text (optional, not all providers support this).

        Args:
            text: The input string or list of strings for which to generate embeddings
            model_name: Name of the embedding model to use (optional, provider-specific)
            **kwargs: Additional provider-specific parameters

        Returns:
            List of embeddings (floats) for single text, or list of lists for multiple texts

        Raises:
            NotImplementedError: If the provider doesn't support embeddings
            ImportError: If the provider library is not available
            ValueError: If the request fails
        """
        raise NotImplementedError(
            f"{self.get_provider_name()} adapter does not support embedding generation"
        )

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available (library installed).

        Returns:
            True if the provider library is available, False otherwise
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.

        Returns:
            Provider name (e.g., "litellm", "ollama")
        """
        pass
