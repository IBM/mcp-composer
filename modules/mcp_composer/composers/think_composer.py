"""Think Composer — sequential thinking for one problem at a time.

Member servers from the usual composer config are still mounted, so research
or domain tools can sit beside ``sequential_thinking``. This process binds
``127.0.0.1`` only.

Environment:

- ``MCP_MODE``: ``http`` (default), ``sse``, or ``stdio``
- ``MCP_HOST``: loopback name, default ``127.0.0.1``
- ``MCP_PORT``: default ``9000``
"""

from __future__ import annotations

import asyncio

from mcp_composer import MCPComposer
from mcp_composer.core.domain_composer import (
    THINK_COMPOSER_NAME,
    configure_think_composer,
    serve_domain_composer,
)


async def main() -> None:
    composer = MCPComposer(name=THINK_COMPOSER_NAME)
    await configure_think_composer(composer)
    await serve_domain_composer(composer)


if __name__ == "__main__":
    asyncio.run(main())
