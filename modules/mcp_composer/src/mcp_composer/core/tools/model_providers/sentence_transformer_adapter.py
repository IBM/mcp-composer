"""
SentenceTransformer Embedding Provider Adapter

Adapter for using sentence-transformers library for embeddings.
"""

from typing import Any, Dict, List, Optional, Union
from .base import ModelProviderAdapter
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

SentenceTransformer: Any = None

# Try to import sentence-transformers, but handle gracefully if not available
try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "sentence-transformers not available. Please install it with: pip install sentence-transformers"
    )


class SentenceTransformerAdapter(ModelProviderAdapter):
    """
    SentenceTransformer adapter for embedding generation.

    This adapter uses the sentence-transformers library for local embedding generation.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the SentenceTransformer adapter.

        Args:
            model_name: Name of the sentence-transformers model to use
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is not available. Please install it with: pip install sentence-transformers"
            )

        self.model_name = model_name
        try:
            self.model = SentenceTransformer(model_name)
            logger.info("Loaded SentenceTransformer model: %s", model_name)
        except Exception as e:
            logger.error(
                "Failed to load SentenceTransformer model '%s': %s", model_name, e
            )
            raise

    async def chat(
        self,
        model_name: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        options: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Chat is not supported by SentenceTransformer (embedding-only provider).

        Raises:
            NotImplementedError: Always, as SentenceTransformer only supports embeddings
        """
        raise NotImplementedError(
            "SentenceTransformer adapter only supports embedding generation, not chat"
        )

    def encode(
        self, text: Union[str, List[str]], model_name: Optional[str] = None, **kwargs
    ) -> Union[List[float], List[List[float]]]:
        """
        Generate embeddings using SentenceTransformer.

        Args:
            text: The input string or list of strings for which to generate embeddings
            model_name: Optional model name (ignored, uses model from initialization)
            **kwargs: Additional parameters passed to model.encode()

        Returns:
            List of embeddings (floats) for single text, or list of lists for multiple texts
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers is not available")

        try:
            # Generate embeddings
            embeddings = self.model.encode(text, **kwargs)

            # Convert numpy array to list
            if isinstance(text, str):
                return embeddings.tolist()
            else:
                return [emb.tolist() for emb in embeddings]

        except Exception as e:
            logger.error("Error generating embeddings with SentenceTransformer: %s", e)
            raise ValueError(f"Failed to generate embeddings: {e}")

    def is_available(self) -> bool:
        """Check if sentence-transformers is available."""
        return SENTENCE_TRANSFORMERS_AVAILABLE

    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "sentence-transformers"
