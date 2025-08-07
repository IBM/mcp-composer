import pytest
from unittest.mock import patch, MagicMock
import mcp_composer_client.acp_server as acp_server


def test_run_invokes_server():
    with patch.object(acp_server, "server") as mock_server:
        acp_server.run()
        mock_server.run.assert_called()


# More advanced async tests for mcp_composer_chatbot can be added with pytest-asyncio
