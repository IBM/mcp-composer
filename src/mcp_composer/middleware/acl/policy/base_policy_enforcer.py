from abc import ABC, abstractmethod
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class BasePolicyEnforcer(ABC):
    """
    Abstract base class for all policy enforcers.
    Implementations must define the is_allowed method.
    """

    @abstractmethod
    def is_allowed(self, tool_name: str, context: dict) -> bool:
        """Check if access is allowed for the given tool and context."""
        pass
