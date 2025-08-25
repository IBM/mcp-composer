"""
Storage module for MCP Composer.

This module provides database interfaces and storage adapters including:
- DatabaseInterface: Abstract base class for database operations
- LocalFileAdapter: Local file-based storage implementation
- CloudantAdapter: IBM Cloudant cloud database implementation for storing configurations
- FakeDatabase: In-memory database for testing
"""

from .database import DatabaseInterface
from .local_file_adapter import LocalFileAdapter
from .cloudant_adapter import CloudantAdapter
from .fake_database import FakeDatabase

__all__ = [
    "DatabaseInterface",
    "LocalFileAdapter", 
    "CloudantAdapter",
    "FakeDatabase",
]
