"""Compatibility entry for Think Composer.

Prefer ``composers/think_composer.py``. This module keeps the older filename
working and runs the same process.
"""

from __future__ import annotations

import asyncio

from think_composer import main

if __name__ == "__main__":
    asyncio.run(main())
