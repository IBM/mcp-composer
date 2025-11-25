"""
Project generator for MCP Composer initialization.

This module handles the generation of project structure, configuration files,
and example files for new MCP Composer projects.
"""

import json
from pathlib import Path
from typing import Dict, Any

from rich import print as rprint

from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class ProjectGenerator:
    """Generates MCP Composer project structure and files."""

    def __init__(self, config: Dict[str, Any], target_dir: Path):
        """
        Initialize the project generator.

        Args:
            config: Project configuration dictionary
            target_dir: Target directory for the project
        """
        self.config = config
        self.target_dir = target_dir
        self.project_name = config["project_name"]

    def generate(self) -> None:
        """Generate the complete project structure."""
        rprint("[cyan]📁 Creating project structure...[/cyan]")
        self._create_directory_structure()

        rprint("[cyan]📝 Generating configuration files...[/cyan]")
        self._create_config_files()

        rprint("[cyan]🐍 Creating Python files...[/cyan]")
        self._create_python_files()

        if self.config.get("with_examples"):
            rprint("[cyan]📚 Adding example files...[/cyan]")
            self._create_example_files()

        rprint("[cyan]📄 Creating documentation...[/cyan]")
        self._create_documentation()

        rprint("[green]✅ Project structure created successfully![/green]")

    def _create_directory_structure(self) -> None:
        """Create the project directory structure."""
        directories = [
            self.target_dir,
            self.target_dir / "config",
            self.target_dir / "middleware",
            self.target_dir / "tools",
            self.target_dir / "prompts",
            self.target_dir / "logs",
            self.target_dir / "data",
        ]

        if self.config.get("with_examples"):
            directories.extend(
                [
                    self.target_dir / "examples",
                    self.target_dir / "examples" / "tools",
                    self.target_dir / "examples" / "middleware",
                    self.target_dir / "examples" / "configs",
                ]
            )

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info("Created directory: %s", directory)

    def _create_config_files(self) -> None:
        """Create configuration files."""
        # Create main config.json
        config_json = self._generate_main_config()
        config_path = self.target_dir / "config" / "config.json"
        self._write_json_file(config_path, config_json)

        # Create middleware config
        middleware_config = self._generate_middleware_config()
        middleware_path = self.target_dir / "config" / "middleware.json"
        self._write_json_file(middleware_path, middleware_config)

        # Create .env file
        env_content = self._generate_env_file()
        env_path = self.target_dir / ".env"
        self._write_text_file(env_path, env_content)

        # Create .env.example
        env_example_path = self.target_dir / ".env.example"
        self._write_text_file(env_example_path, env_content)

        # Create .gitignore
        gitignore_content = self._generate_gitignore()
        gitignore_path = self.target_dir / ".gitignore"
        self._write_text_file(gitignore_path, gitignore_content)

    def _create_python_files(self) -> None:
        """Create Python files."""
        # Create __init__.py
        init_path = self.target_dir / "__init__.py"
        self._write_text_file(init_path, '"""MCP Composer project."""\n')

        # Create server.py (main entry point)
        server_content = self._generate_server_file()
        server_path = self.target_dir / "server.py"
        self._write_text_file(server_path, server_content)

        # Create pyproject.toml
        pyproject_content = self._generate_pyproject_toml()
        pyproject_path = self.target_dir / "pyproject.toml"
        self._write_text_file(pyproject_path, pyproject_content)

        # Create requirements.txt
        requirements_content = self._generate_requirements()
        requirements_path = self.target_dir / "requirements.txt"
        self._write_text_file(requirements_path, requirements_content)

    def _create_example_files(self) -> None:
        """Create example files."""
        # Example tool
        example_tool = self._generate_example_tool()
        tool_path = self.target_dir / "examples" / "tools" / "example_tool.py"
        self._write_text_file(tool_path, example_tool)

        # Example middleware
        example_middleware = self._generate_example_middleware()
        middleware_path = self.target_dir / "examples" / "middleware" / "example_middleware.py"
        self._write_text_file(middleware_path, example_middleware)

        # Example config
        example_config = self._generate_example_config()
        config_path = self.target_dir / "examples" / "configs" / "example_config.json"
        self._write_json_file(config_path, example_config)

    def _create_documentation(self) -> None:
        """Create documentation files."""
        # README.md
        readme_content = self._generate_readme()
        readme_path = self.target_dir / "README.md"
        self._write_text_file(readme_path, readme_content)

        # CONTRIBUTING.md (if with_examples)
        if self.config.get("with_examples"):
            contributing_content = self._generate_contributing()
            contributing_path = self.target_dir / "CONTRIBUTING.md"
            self._write_text_file(contributing_path, contributing_content)

    def _generate_main_config(self) -> Dict:
        """Generate main configuration file content."""
        mode = self.config["mode"]

        config = {
            "project": {
                "name": self.config["project_name"],
                "description": self.config["description"],
                "version": "0.1.0",
            },
            "servers": [],
        }

        # Add example server configuration based on mode
        if mode == "stdio":
            config["servers"].append(
                {
                    "id": "example-server",
                    "type": "stdio",
                    "command": "python",
                    "args": ["server.py"],
                    "label": "Example STDIO Server",
                    "enabled": True,
                }
            )
        elif mode == "local":
            config["servers"].append(
                {
                    "id": "example-local-server",
                    "type": "local",
                    "command": "python",
                    "args": ["server.py"],
                    "cwd": ".",
                    "label": "Example Local Server",
                    "enabled": True,
                }
            )
        elif mode in ["http", "sse"]:
            config["servers"].append(
                {
                    "id": "example-server",
                    "type": mode,
                    "endpoint": f"http://{self.config['host']}:{self.config['port']}",
                    "label": f"Example {mode.upper()} Server",
                    "enabled": True,
                }
            )
        elif mode == "openapi":
            config["servers"].append(
                {
                    "id": "example-api-server",
                    "type": "openapi",
                    "open_api": {
                        "spec_url": "https://api.example.com/openapi.json",
                        "base_url": "https://api.example.com",
                    },
                    "label": "Example OpenAPI Server",
                    "enabled": True,
                }
            )
        elif mode == "graphql":
            config["servers"].append(
                {
                    "id": "example-graphql-server",
                    "type": "graphql",
                    "endpoint": f"http://{self.config['host']}:{self.config['port']}/graphql",
                    "label": "Example GraphQL Server",
                    "enabled": True,
                }
            )
        elif mode == "client":
            config["servers"].append(
                {
                    "id": "example-client-server",
                    "type": "client",
                    "endpoint": f"http://{self.config['host']}:{self.config['port']}",
                    "label": "Example Client Server",
                    "enabled": True,
                }
            )

        return config

    def _generate_middleware_config(self) -> Dict:
        """Generate middleware configuration."""
        return {"middleware": [], "middleware_settings": {"enabled": True}}

    def _generate_env_file(self) -> str:
        """Generate .env file content."""
        lines = [
            "# MCP Composer Environment Configuration",
            f"# Project: {self.config['project_name']}",
            "",
            "# Server Configuration",
            f"MCP_MODE={self.config['mode']}",
        ]

        if self.config["mode"] in ["http", "sse"]:
            lines.extend(
                [
                    f"MCP_HOST={self.config['host']}",
                    f"MCP_PORT={self.config['port']}",
                ]
            )

        # Authentication
        if self.config["auth_type"] == "oauth":
            lines.extend(
                [
                    "",
                    "# OAuth Configuration",
                    "ENABLE_OAUTH=False",
                    "OAUTH_CLIENT_ID=your_client_id",
                    "OAUTH_CLIENT_SECRET=your_client_secret",
                    "OAUTH_AUTH_URL=https://auth.example.com/authorize",
                    "OAUTH_TOKEN_URL=https://auth.example.com/token",
                    "OAUTH_CALLBACK_PATH=http://localhost:9000/auth/callback",
                ]
            )

        # Database
        if self.config["database"] == "postgres":
            lines.extend(
                [
                    "",
                    "# Database Configuration",
                    "DATABASE_TYPE=postgres",
                    "DATABASE_HOST=localhost",
                    "DATABASE_PORT=5432",
                    "DATABASE_NAME=mcp_composer",
                    "DATABASE_USER=postgres",
                    "DATABASE_PASSWORD=postgres",
                ]
            )
        elif self.config["database"] == "sqlite":
            lines.extend(
                [
                    "",
                    "# Database Configuration",
                    "DATABASE_TYPE=sqlite",
                    "DATABASE_PATH=data/mcp_composer.db",
                ]
            )

        lines.extend(
            [
                "",
                "# Logging",
                "LOG_LEVEL=INFO",
                "LOG_FILE=logs/mcp_composer.log",
                "",
                "# Paths",
                "CONFIG_PATH=config/config.json",
                "MIDDLEWARE_CONFIG_PATH=config/middleware.json",
                "",
            ]
        )

        return "\n".join(lines)

    def _generate_gitignore(self) -> str:
        """Generate .gitignore content."""
        return """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# Environment
.env
.env.local

# Logs
logs/
*.log

# Data
data/
*.db
*.sqlite
*.sqlite3

# OS
.DS_Store
Thumbs.db

# MCP Composer
mcp_composer.log
member_servers.json
*.pid
"""

    def _generate_server_file(self) -> str:
        """Generate server.py content."""
        mode = self.config["mode"]

        # Build mode-specific startup code
        mode_startup = ""
        if mode == "stdio":
            mode_startup = """    if mode == "stdio":
        logger.info("Starting in STDIO mode")
        await composer.run_stdio_async()"""
        elif mode == "local":
            mode_startup = """    if mode == "local":
        logger.info("Starting in LOCAL mode")
        await composer.run_stdio_async()"""
        elif mode == "sse":
            mode_startup = f'''    if mode == "sse":
        host = os.getenv("MCP_HOST", "{self.config.get("host", "0.0.0.0")}")
        port = int(os.getenv("MCP_PORT", "{self.config.get("port", 9000)}"))
        logger.info(f"Starting in SSE mode on {{host}}:{{port}}")
        await composer.run_sse_async(host=host, port=port, path="/sse")'''
        elif mode == "http":
            mode_startup = f'''    if mode == "http":
        host = os.getenv("MCP_HOST", "{self.config.get("host", "0.0.0.0")}")
        port = int(os.getenv("MCP_PORT", "{self.config.get("port", 9000)}"))
        logger.info(f"Starting in HTTP mode on {{host}}:{{port}}")
        await composer.run_http_async(host=host, port=port, path="/mcp")'''
        elif mode == "openapi":
            mode_startup = """    if mode == "openapi":
        logger.info("Starting in OpenAPI mode")
        # OpenAPI servers are configured via config.json
        logger.info("OpenAPI server configured - access via composer tools")
        await composer.run_stdio_async()"""
        elif mode == "graphql":
            mode_startup = f'''    if mode == "graphql":
        host = os.getenv("MCP_HOST", "{self.config.get("host", "0.0.0.0")}")
        port = int(os.getenv("MCP_PORT", "{self.config.get("port", 9000)}"))
        logger.info(f"Starting in GraphQL mode on {{host}}:{{port}}")
        await composer.run_http_async(host=host, port=port, path="/graphql")'''
        elif mode == "client":
            mode_startup = f'''    if mode == "client":
        host = os.getenv("MCP_HOST", "{self.config.get("host", "0.0.0.0")}")
        port = int(os.getenv("MCP_PORT", "{self.config.get("port", 9000)}"))
        logger.info(f"Starting in CLIENT mode on {{host}}:{{port}}")
        await composer.run_http_async(host=host, port=port, path="/mcp")'''
        else:
            mode_startup = """    if mode == "stdio":
        await composer.run_stdio_async()"""

        content = f'''"""
{self.config["project_name"]} - MCP Composer Server

{self.config["description"]}
"""

import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

from mcp_composer import MCPComposer
from mcp_composer.core.utils.logger import LoggerFactory

# Load environment variables
load_dotenv()

# Initialize logger
logger = LoggerFactory.get_logger()


async def main():
    """Main entry point for the MCP Composer server."""
    logger.info("Starting {self.config["project_name"]}...")
    
    # Load configuration
    config_path = os.getenv("CONFIG_PATH", "config/config.json")
    logger.info(f"Loading configuration from {{config_path}}")
    
    # Create MCP Composer instance
    composer = MCPComposer(
        name="{self.config["project_name"]}",
        config_path=config_path
    )
    
    # Setup member servers
    await composer.setup_member_servers()
    
    # Start server based on mode
    mode = os.getenv("MCP_MODE", "{mode}")
    
{mode_startup}
    else:
        logger.error(f"Unknown mode: {{mode}}")
        raise ValueError(f"Unknown mode: {{mode}}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Server error: {{e}}")
        raise
'''
        return content

    def _generate_pyproject_toml(self) -> str:
        """Generate pyproject.toml content."""
        return f'''[project]
name = "{self.config["project_name"]}"
version = "0.1.0"
description = "{self.config["description"]}"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "mcp-composer>=0.1.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]

[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
# Only include server.py and __init__.py, exclude data directories
py-modules = []
packages = []

[tool.setuptools.package-data]
"*" = ["*.json", "*.yaml", "*.yml", "*.md"]

[tool.black]
line-length = 120
target-version = ["py311"]

[tool.ruff]
line-length = 120
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
'''

    def _generate_requirements(self) -> str:
        """Generate requirements.txt content."""
        return """mcp-composer>=0.1.0
python-dotenv>=1.0.0
"""

    def _generate_example_tool(self) -> str:
        """Generate example tool content."""
        return '''"""
Example tool for MCP Composer.

This is a simple example tool that demonstrates how to create custom tools.
"""

from typing import Dict, Any


def example_tool(name: str = "World") -> Dict[str, Any]:
    """
    Example tool that greets a user.
    
    Args:
        name: Name to greet
        
    Returns:
        A greeting message
    """
    return {
        "message": f"Hello, {name}!",
        "status": "success"
    }


async def async_example_tool(name: str = "World") -> Dict[str, Any]:
    """
    Async example tool that greets a user.
    
    Args:
        name: Name to greet
        
    Returns:
        A greeting message
    """
    return {
        "message": f"Hello from async, {name}!",
        "status": "success"
    }
'''

    def _generate_example_middleware(self) -> str:
        """Generate example middleware content."""
        return '''"""
Example middleware for MCP Composer.

This is a simple example middleware that demonstrates how to create custom middleware.
"""

from typing import Any, Callable, Awaitable
from mcp_composer.middleware.base_middleware import BaseMiddleware


class ExampleMiddleware(BaseMiddleware):
    """Example middleware that logs requests."""
    
    async def on_call_tool(
        self,
        tool_name: str,
        arguments: dict,
        next: Callable[..., Awaitable[Any]]
    ) -> Any:
        """
        Hook that runs before tool execution.
        
        Args:
            tool_name: Name of the tool being called
            arguments: Arguments passed to the tool
            next: Next middleware in the chain
            
        Returns:
            Result from the tool execution
        """
        self.logger.info(f"Calling tool: {tool_name} with args: {arguments}")
        
        # Call the next middleware/tool
        result = await next(tool_name, arguments)
        
        self.logger.info(f"Tool {tool_name} returned: {result}")
        
        return result
'''

    def _generate_example_config(self) -> Dict:
        """Generate example configuration."""
        return {
            "description": "Example configuration for MCP Composer",
            "servers": [
                {
                    "id": "example-1",
                    "type": "stdio",
                    "command": "python",
                    "args": ["example_server.py"],
                    "label": "Example Server 1",
                }
            ],
            "middleware": [
                {
                    "name": "ExampleMiddleware",
                    "kind": "examples.middleware.example_middleware.ExampleMiddleware",
                    "mode": "enabled",
                    "priority": 100,
                    "applied_hooks": ["on_call_tool"],
                    "conditions": {"include_tools": ["*"]},
                }
            ],
        }

    def _generate_readme(self) -> str:
        """Generate README.md content."""
        mode = self.config["mode"]

        start_command = f"mcp-composer run --mode {mode}"
        if mode in ["http", "sse"]:
            start_command += f" --host {self.config['host']} --port {self.config['port']}"
        start_command += " --config-path config/config.json"

        return f"""# {self.config["project_name"]}

{self.config["description"]}

## Overview

This project was initialized using MCP Composer's `init` command. It provides a ready-to-run
MCP (Model Context Protocol) Composer setup with configuration files, project structure, and
{" example files" if self.config.get("with_examples") else "a clean starting point"}.

## Project Structure

```
{self.config["project_name"]}/
├── config/              # Configuration files
│   ├── config.json      # Main MCP Composer configuration
│   └── middleware.json  # Middleware configuration
├── middleware/          # Custom middleware implementations
├── tools/              # Custom tool implementations
├── prompts/            # Custom prompts
├── logs/               # Application logs
├── data/               # Data storage
{"├── examples/          # Example files and configurations" if self.config.get("with_examples") else ""}
├── .env                # Environment variables
├── .env.example        # Example environment variables
├── .gitignore          # Git ignore file
├── server.py           # Main server entry point
├── pyproject.toml      # Project metadata and dependencies
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Configuration

- **Mode**: {mode}
{"- **Host**: " + str(self.config["host"]) if mode in ["http", "sse"] else ""}
{"- **Port**: " + str(self.config["port"]) if mode in ["http", "sse"] else ""}
- **Authentication**: {self.config["auth_type"]}
- **Database**: {self.config["database"]}
- **Adapter**: {self.config["adapter"]}

## Getting Started

### Prerequisites

- Python 3.11 or higher
- uv package manager (recommended) or pip

### Installation

1. Install dependencies:

```bash
# Using uv (recommended)
uv pip install -e .

# Or using pip
pip install -r requirements.txt
```

2. Configure environment variables:

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### Running the Server

```bash
# Using the generated server.py
python server.py

# Or using mcp-composer CLI directly
{start_command}
```

{"### Server Access" if mode in ["http", "sse"] else ""}
{
            ""
            if mode == "stdio"
            else f'''
Once the server is running, you can access it at:

- URL: http://{self.config["host"]}:{self.config["port"]}
{"- SSE Endpoint: /sse" if mode == "sse" else ""}
{"- HTTP Endpoint: /mcp" if mode == "http" else ""}
'''
        }

## Development

### Adding Tools

1. Create a new tool in the `tools/` directory
2. Register it in `config/config.json`
3. Restart the server

### Adding Middleware

1. Create a new middleware in the `middleware/` directory
2. Register it in `config/middleware.json`
3. Restart the server

### Adding Prompts

1. Create a new prompt in the `prompts/` directory
2. Register it in `config/config.json`
3. Restart the server

{"## Examples" if self.config.get("with_examples") else ""}
{
            ""
            if not self.config.get("with_examples")
            else '''
Check the `examples/` directory for:

- Example tools (`examples/tools/`)
- Example middleware (`examples/middleware/`)
- Example configurations (`examples/configs/`)
'''
        }

## Logging

Logs are stored in the `logs/` directory. You can configure log level and output in `.env`:

```bash
LOG_LEVEL=INFO
LOG_FILE=logs/mcp_composer.log
```

## Troubleshooting

### Common Issues

1. **Port already in use**: Change the port in `.env` or `config/config.json`
2. **Permission denied**: Ensure the project directory has proper permissions
3. **Module not found**: Make sure dependencies are installed with `uv pip install -e .`

### Getting Help

- Run `mcp-composer --help` for CLI help
- Check the logs in `logs/mcp_composer.log`
- Visit the MCP Composer documentation

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
"""

    def _generate_contributing(self) -> str:
        """Generate CONTRIBUTING.md content."""
        return f"""# Contributing to {self.config["project_name"]}

Thank you for your interest in contributing to this project!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone <your-fork-url>`
3. Create a new branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Test your changes
6. Commit your changes: `git commit -m "Add your commit message"`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Open a pull request

## Development Setup

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .

# Lint code
ruff check .
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Write docstrings for all public functions and classes
- Keep lines under 120 characters

## Testing

- Write tests for new features
- Ensure all tests pass before submitting a PR
- Aim for good test coverage

## Pull Request Process

1. Update the README.md with details of changes if needed
2. Update the CHANGELOG.md if applicable
3. Ensure all tests pass
4. Request review from maintainers

## Questions?

Feel free to open an issue for any questions or concerns.
"""

    def _write_text_file(self, path: Path, content: str) -> None:
        """Write text content to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Created file: %s", path)

    def _write_json_file(self, path: Path, content: Dict) -> None:
        """Write JSON content to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2)
            f.write("\n")
        logger.info("Created file: %s", path)
