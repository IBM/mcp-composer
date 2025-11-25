"""Configuration loader for unified MCP Composer configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from mcp_composer.core.config.unified_config import (
    UnifiedConfig,
    ConfigSection,
    ConfigValidationError,
    UnifiedConfigValidator,
    ServerConfig,
    MiddlewareConfig,
    PromptConfig,
    ToolConfig
)
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class ConfigLoader:
    """Loads and applies unified configuration to MCP Composer."""

    def __init__(self, composer=None):
        self.composer = composer
        self.logger = logger
        self._file_cache = {}  # Cache for loaded files to avoid duplicate reads

    def _detect_file_type(self, file_path: str) -> str:
        """Detect file type based on extension."""
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext in ['.yaml', '.yml']:
            return 'yaml'
        if ext == '.json':
            return 'json'

        # Default to JSON if extension is not recognized
        self.logger.warning("Unknown file extension '%s', defaulting to JSON parsing", ext)
        return 'json'

    def _load_file_data(self, file_path: str) -> dict:
        """Load data from JSON or YAML file."""
        file_type = self._detect_file_type(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_type == 'yaml':
                    return yaml.safe_load(f)
                return json.load(f)
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"Invalid YAML in configuration file: {e}") from e
        except json.JSONDecodeError as e:
            raise ConfigValidationError(f"Invalid JSON in configuration file: {e}") from e
        except OSError as e:
            raise ConfigValidationError(f"Failed to load configuration file: {e}") from e

    def load_from_file(self, file_path: str, config_type: str = "all") -> UnifiedConfig:
        """Load configuration from a JSON or YAML file with caching."""
        try:
            # Use cached data if available
            if file_path in self._file_cache:
                config_data = self._file_cache[file_path]
            else:
                config_data = self._load_file_data(file_path)
                self._file_cache[file_path] = config_data

            # Handle different config types
            if config_type == "all":
                # Full unified configuration
                validator = UnifiedConfigValidator(config_data)
                validator.validate()
                file_type = self._detect_file_type(file_path)
                self.logger.info(f"Successfully loaded unified configuration from {file_path} ({file_type})")
                return validator.config
            else:
                # Single section configuration
                return self._load_single_section(config_data, config_type, file_path)

        except FileNotFoundError as exc:
            raise ConfigValidationError(f"Configuration file not found: {file_path}") from exc
        except ConfigValidationError:
            raise
        except Exception as e:
            raise ConfigValidationError(f"Failed to load configuration: {e}") from e

    def detect_config_type(self, file_path: str) -> str:
        """Auto-detect configuration type based on file content with caching."""
        try:
            # Use cached data if available
            if file_path in self._file_cache:
                config_data = self._file_cache[file_path]
            else:
                config_data = self._load_file_data(file_path)
                self._file_cache[file_path] = config_data

            return self._detect_config_type_from_data(config_data, file_path)

        except FileNotFoundError as exc:
            raise ConfigValidationError(f"Configuration file not found: {file_path}") from exc
        except ConfigValidationError:
            raise
        except Exception as e:
            raise ConfigValidationError(f"Failed to detect configuration type: {e}") from e

    def _detect_config_type_from_data(self, config_data: dict, file_path: str) -> str:
        """Detect configuration type from already loaded data."""
        # Check if it's a unified config (has multiple sections)
        if isinstance(config_data, dict):
            if any(key in config_data for key in ['servers', 'middleware', 'prompts', 'tools']):
                return "all"
            if self._looks_like_tools_config(config_data):
                return "tools"

            raise ConfigValidationError(
                "Unable to detect configuration type. "
                "Expected one of: servers (list), middleware (list), prompts (list), tools (dict), or unified (dict with sections). "
                f"Got dictionary with keys: {list(config_data.keys())}"
            )

        # Check if it's a list (single section)
        if isinstance(config_data, list):
            if not config_data:
                raise ConfigValidationError("Empty configuration file")

            # Check first item to determine type based on mandatory fields
            first_item = config_data[0]
            if not isinstance(first_item, dict):
                raise ConfigValidationError("Configuration items must be dictionaries")

            # Check for server mandatory fields
            if all(field in first_item for field in ['id', 'type', 'endpoint']):
                return "servers"

            # Check for middleware mandatory fields
            if all(field in first_item for field in ['name', 'kind', 'mode']):
                return "middleware"

            # Check for prompt mandatory fields
            if all(field in first_item for field in ['name', 'description', 'template']):
                return "prompts"

            raise ConfigValidationError(
                "Unable to detect configuration type. Missing mandatory fields for servers, middleware, or prompts"
            )

        # This should never be reached due to the isinstance checks above
        raise ConfigValidationError("Configuration must be a JSON object or array")

    def _looks_like_tools_config(self, config_data: dict) -> bool:
        """Check if a dictionary looks like a tools configuration."""
        if not config_data:
            return False

        # Count how many values look like tool definitions vs other types
        tool_like_count = 0
        total_count = len(config_data)

        for key, value in config_data.items():
            if not isinstance(value, dict):
                continue

            # Check if it looks like a server config (has id, type, endpoint) - check this first
            if all(field in value for field in ['id', 'type', 'endpoint']):
                # This is a server config, not a tool config
                continue
            # Check for common tool definition patterns
            # OpenAPI tools have 'openapi' field
            elif 'openapi' in value:
                tool_like_count += 1
                continue
            # Custom tools might have 'tool_type' field
            elif 'tool_type' in value:
                tool_like_count += 1
                continue
            # Other tool patterns (but exclude server configs)
            elif any(field in value for field in ['name', 'description', 'spec']):
                tool_like_count += 1
                continue
            # Check if it's a list (like mock_update_tool_description)
            elif isinstance(value, list):
                # This is likely a list of server configs, not a tool config
                continue

        # If more than half of the entries look like tool definitions, consider it a tools config
        # This handles mixed content files where some entries are tools and others are server configs
        return tool_like_count > 0 and (tool_like_count >= total_count / 2 or tool_like_count >= 2)

    def _load_single_section(self, config_data: dict, config_type: str, file_path: str) -> UnifiedConfig:
        """Load a single section configuration and wrap it in UnifiedConfig."""
        # Configuration type mapping for cleaner code
        config_mappings = {
            "servers": (ServerConfig, "servers"),
            "middleware": (MiddlewareConfig, "middleware"),
            "prompts": (PromptConfig, "prompts")
        }

        # Handle list format (for servers, middleware, prompts)
        if isinstance(config_data, list):
            if config_type in config_mappings:
                config_class, section_name = config_mappings[config_type]
                items = self._validate_and_convert_list(config_data, config_class, config_type)

                # Create UnifiedConfig with the appropriate section populated
                unified_config = UnifiedConfig(servers=[], middleware=[], prompts=[], tools={})
                setattr(unified_config, section_name, items)
                return unified_config
            else:
                raise ConfigValidationError(f"Unsupported config type for list format: {config_type}")

        # Handle dict format (for tools)
        elif isinstance(config_data, dict):
            if config_type == "tools":
                tools = self._validate_and_convert_dict(config_data, ToolConfig, "tools")
                return UnifiedConfig(servers=[], middleware=[], prompts=[], tools=tools)
            else:
                raise ConfigValidationError(f"Unsupported config type for dict format: {config_type}")

        else:
            raise ConfigValidationError(f"Configuration must be a list or dictionary, got {type(config_data)}")

    def _validate_and_convert_list(self, data_list: list, config_class, config_type: str) -> list:
        """Validate and convert a list of configurations to the appropriate config class."""
        items = []
        for i, item_data in enumerate(data_list):
            if not isinstance(item_data, dict):
                raise ConfigValidationError(f"{config_type.title()} configuration at index {i} must be a dictionary, got {type(item_data)}")
            try:
                items.append(config_class(**item_data))
            except Exception as e:
                raise ConfigValidationError(f"Invalid {config_type} configuration at index {i}: {e}")
        return items

    def _validate_and_convert_dict(self, data_dict: dict, config_class, config_type: str) -> dict:
        """Validate and convert a dictionary of configurations to the appropriate config class."""
        items = {}
        for key, item_data in data_dict.items():
            # For tools config, skip non-tool entries during validation
            if config_type == "tools":
                if not self._is_tool_config(item_data):
                    # Skip non-tool entries (server configs, lists, etc.)
                    continue

                if not isinstance(item_data, dict):
                    raise ConfigValidationError(
                        f"Tool configuration for '{key}' must be a dictionary (OpenAPI spec or tool definition), "
                        f"got {type(item_data)}. "
                        f"Expected format: {{'openapi': '3.0.3', 'info': {{...}}}} or {{'tool_type': 'custom', ...}}"
                    )
            else:
                # For other config types, enforce dictionary requirement
                if not isinstance(item_data, dict):
                    raise ConfigValidationError(f"{config_type.title()} configuration for '{key}' must be a dictionary, got {type(item_data)}")

            try:
                items[key] = config_class(**item_data)
            except Exception as e:
                # For tools, provide more specific error message
                if config_type == "tools":
                    raise ConfigValidationError(
                        f"Invalid tool configuration for '{key}': {e}. "
                        f"Tool configurations should contain OpenAPI specifications or tool definitions. "
                        f"Check that the configuration has the required fields for the tool type."
                    ) from e
                raise ConfigValidationError(f"Invalid {config_type} configuration for '{key}': {e}") from e
        return items

    async def apply_config(
        self,
        config: UnifiedConfig,
        sections: Optional[List[ConfigSection]] = None
    ) -> Dict[str, Any]:
        """
        Apply configuration to MCP Composer.

        Args:
            config: Unified configuration to apply
            sections: List of sections to apply (None means apply all)

        Returns:
            Dictionary with results of applying each section
        """
        if not self.composer:
            raise ValueError("Composer instance is required to apply configuration")

        if sections is None:
            sections = [ConfigSection.SERVERS, ConfigSection.MIDDLEWARE, ConfigSection.PROMPTS, ConfigSection.TOOLS]

        results = {}

        # Apply servers
        if ConfigSection.SERVERS in sections and config.servers:
            results['servers'] = await self._apply_servers(config.servers)

        # Apply middleware
        if ConfigSection.MIDDLEWARE in sections and config.middleware:
            results['middleware'] = await self._apply_middleware(config.middleware)

        # Apply prompts
        if ConfigSection.PROMPTS in sections and config.prompts:
            results['prompts'] = await self._apply_prompts(config.prompts)

        # Apply tools
        if ConfigSection.TOOLS in sections and config.tools:
            results['tools'] = await self._apply_tools(config.tools)

        return results

    async def _apply_servers(self, servers: List[Any]) -> Dict[str, Any]:
        """Apply server configurations with optimized error handling."""
        results = {
            'registered': [],
            'failed': [],
            'total': len(servers)
        }

        for server_config in servers:
            try:
                # Convert to dict and fix OAuth2 field mapping
                server_dict = self._prepare_server_config(server_config)

                # Register the server
                result = await self.composer._mount_member_server(server_dict)
                results['registered'].append({
                    'id': server_config.id,
                    'type': server_config.type,
                    'result': result
                })
                self.logger.info(f"Successfully registered server: {server_config.id}")

            except Exception as e:
                error_info = {
                    'id': getattr(server_config, 'id', 'unknown'),
                    'type': getattr(server_config, 'type', 'unknown'),
                    'error': str(e)
                }
                results['failed'].append(error_info)
                self.logger.error(f"Failed to register server {error_info['id']}: {e}")

        return results

    def _prepare_server_config(self, server_config: Any) -> dict:
        """Prepare server configuration with OAuth2 field mapping."""
        server_dict = server_config.model_dump()

        # Fix OAuth2 field mapping for compatibility
        if server_dict.get("auth_strategy") == "oauth2":
            server_dict["auth_strategy"] = "oauth"
            if server_dict.get("auth"):
                auth = server_dict["auth"]
                # Map field names to match validator expectations
                field_mappings = {
                    "clientId": "client_id",
                    "clientSecret": "client_secret",
                    "refreshToken": "refresh_token"
                }
                for old_key, new_key in field_mappings.items():
                    if old_key in auth:
                        auth[new_key] = auth.pop(old_key)

        return server_dict

    async def _apply_middleware(self, middleware_configs: List[Any]) -> Dict[str, Any]:
        """Apply middleware configurations."""
        results = {
            'registered': [],
            'failed': [],
            'total': len(middleware_configs)
        }

        # Convert middleware configs to the format expected by MiddlewareManager
        middleware_entries = []
        for mw_config in middleware_configs:
            try:
                middleware_entry = {
                    'name': mw_config.name,
                    'kind': mw_config.kind,
                    'mode': mw_config.mode,
                    'priority': mw_config.priority,
                    'applied_hooks': mw_config.applied_hooks,
                    'config': mw_config.config or {},
                    'description': mw_config.description or '',
                    'version': mw_config.version or '0.0.0'
                }
                middleware_entries.append(middleware_entry)

            except Exception as e:
                results['failed'].append({
                    'name': getattr(mw_config, 'name', 'unknown'),
                    'error': str(e)
                })
                self.logger.error(f"Failed to process middleware config: {e}")

        # Apply middleware using the existing middleware system
        try:
            # This would need to be integrated with the existing middleware manager
            # For now, we'll just log the middleware configurations
            for entry in middleware_entries:
                results['registered'].append({
                    'name': entry['name'],
                    'kind': entry['kind'],
                    'mode': entry['mode']
                })
                self.logger.info(f"Processed middleware: {entry['name']}")

        except Exception as e:
            self.logger.error(f"Failed to apply middleware: {e}")
            results['failed'].append({'error': str(e)})

        return results

    async def _apply_prompts(self, prompts: List[Any]) -> Dict[str, Any]:
        """Apply prompt configurations."""
        results = {
            'registered': [],
            'failed': [],
            'total': len(prompts)
        }

        # Convert prompts to the format expected by the prompt manager
        prompt_configs = []
        for prompt in prompts:
            try:
                prompt_dict = {
                    'name': prompt.name,
                    'description': prompt.description,
                    'template': prompt.template,
                    'arguments': [arg.model_dump() for arg in prompt.arguments] if prompt.arguments else []
                }
                prompt_configs.append(prompt_dict)

            except Exception as e:
                results['failed'].append({
                    'name': getattr(prompt, 'name', 'unknown'),
                    'error': str(e)
                })
                self.logger.error(f"Failed to process prompt config: {e}")

        # Apply prompts using the existing prompt manager
        try:
            if prompt_configs:
                # Use the correct method name (add_prompts, not add_prompt)
                added_prompts = self.composer._prompt_manager.add_prompts(prompt_configs)
                results['registered'] = [{'name': name} for name in added_prompts]
                self.logger.info(f"Successfully added {len(added_prompts)} prompts")

        except Exception as e:
            self.logger.error(f"Failed to apply prompts: {e}")
            results['failed'].append({'error': str(e)})

        return results

    async def _apply_tools(self, tools: Dict[str, Any]) -> Dict[str, Any]:
        """Apply tool configurations."""
        results = {
            'registered': [],
            'failed': [],
            'skipped': [],
            'total': len(tools)
        }

        for tool_name, tool_config in tools.items():
            try:
                # Convert tool config to dict
                tool_dict = tool_config.model_dump() if hasattr(tool_config, 'model_dump') else tool_config

                # Skip non-tool entries (server configs, lists, etc.)
                if not self._is_tool_config(tool_dict):
                    results['skipped'].append({
                        'name': tool_name,
                        'reason': 'Not a tool configuration (appears to be server config or other)'
                    })
                    self.logger.debug(f"Skipping non-tool entry: {tool_name}")
                    continue

                # Check if it's an OpenAPI tool
                if tool_dict.get('openapi'):
                    # Register OpenAPI tool using the composer's method
                    await self.composer.add_tools_from_openapi(tool_dict)
                    results['registered'].append({
                        'name': tool_name,
                        'type': 'openapi',
                        'status': 'successfully registered'
                    })
                    self.logger.info(f"Successfully registered OpenAPI tool: {tool_name}")

                # Check if it's a custom tool with tool_type
                elif tool_dict.get('tool_type') == 'curl':
                    # Register curl tool
                    await self.composer.add_tools_from_curl(tool_dict)
                    results['registered'].append({
                        'name': tool_name,
                        'type': 'curl',
                        'status': 'successfully registered'
                    })
                    self.logger.info(f"Successfully registered curl tool: {tool_name}")

                elif tool_dict.get('tool_type') == 'script':
                    # Register script tool
                    await self.composer.add_tools_from_python(tool_dict)
                    results['registered'].append({
                        'name': tool_name,
                        'type': 'script',
                        'status': 'successfully registered'
                    })
                    self.logger.info(f"Successfully registered script tool: {tool_name}")

                else:
                    # Unknown tool type
                    results['failed'].append({
                        'name': tool_name,
                        'error': "Unknown tool type. Expected 'openapi', 'curl', or 'script' tool_type"
                    })
                    self.logger.error(f"Unknown tool type for {tool_name}: {tool_dict.get('tool_type', 'none')}")

            except Exception as e:
                results['failed'].append({
                    'name': tool_name,
                    'error': str(e)
                })
                self.logger.error(f"Failed to register tool {tool_name}: {e}")

        return results

    def _is_tool_config(self, config_dict: dict) -> bool:
        """Check if a configuration dictionary is actually a tool configuration."""
        if not isinstance(config_dict, dict):
            return False

        # Check for OpenAPI tool
        if 'openapi' in config_dict:
            return True

        # Check for custom tool types
        if config_dict.get('tool_type') in ['curl', 'script']:
            return True

        # Check for other tool patterns
        if any(field in config_dict for field in ['name', 'description', 'endpoint', 'spec']):
            # But exclude server configs that might have these fields
            if all(field in config_dict for field in ['id', 'type', 'endpoint']):
                return False  # This is a server config
            return True

        return False


class ConfigManager:
    """High-level configuration manager for MCP Composer."""

    def __init__(self, composer=None):
        self.loader = ConfigLoader(composer)
        self.logger = logger

    async def load_and_apply(
        self,
        file_path: str,
        sections: Optional[List[ConfigSection]] = None,
        config_type: str = "all"
    ) -> Dict[str, Any]:
        """
        Load configuration from file and apply it to the composer.

        Args:
            file_path: Path to configuration file
            sections: List of sections to apply (None means apply all)
            config_type: Type of configuration (servers, middleware, prompts, tools, all)

        Returns:
            Dictionary with results of applying each section
        """
        try:
            # Load configuration
            config = self.loader.load_from_file(file_path, config_type)

            # Apply configuration
            results = await self.loader.apply_config(config, sections)

            self.logger.info(f"Successfully loaded and applied {config_type} configuration from {file_path}")
            return results

        except Exception as e:
            self.logger.error(f"Failed to load and apply configuration: {e}")
            raise

    def validate_config_file(self, file_path: str) -> bool:
        """
        Validate a configuration file without applying it.

        Args:
            file_path: Path to configuration file

        Returns:
            True if valid, False otherwise
        """
        try:
            self.loader.load_from_file(file_path)
            self.logger.info(f"Configuration file {file_path} is valid")
            return True
        except Exception as e:
            self.logger.error(f"Configuration file {file_path} is invalid: {e}")
            return False
