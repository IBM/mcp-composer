# CLI Usage

This guide covers the command-line interface (CLI) for MCP Composer.

## Overview

MCP Composer provides a powerful CLI that allows you to:

- Initialize new projects with ready-to-run configurations (init)
- Start the server in different modes (HTTP, SSE, STDIO) (run, composer start)
- Configure server settings and authentication
- Manage middleware configurations (middleware)
- Validate configurations
- Manage tools and servers
- Monitor health and status
- Handle OAuth authentication
- Validate and show configurations (config)

## Installation

### Prerequisites

- Python 3.11+
- uv package manager (recommended) or pip
- python-daemon (for daemon functionality)

### Install from Source

```bash
# Clone the repository
git clone <repository-url>
cd mcp-composer

# Install in development mode
cd modules/mcp_composer
uv pip install -e .

# Add daemon dependency for process management
uv add python-daemon
```

### Verify Installation

```bash
mcp-composer --help
```

## Basic Usage

### Initialize a New Project

The `init` command is the fastest way to get started with MCP Composer. It creates a complete, ready-to-run project structure with configuration files, examples, and documentation.

```bash
# Interactive setup (recommended for first-time users)
mcp-composer init my-project

# Quick setup with defaults
mcp-composer init my-project --defaults

# Setup with examples
mcp-composer init my-project --with-examples

# Cloud deployment setup
mcp-composer init my-project --adapter cloud --mode http --port 8080 --defaults

# Local development setup
mcp-composer init my-project --adapter local --mode stdio --with-examples --defaults

# Setup with authentication
mcp-composer init my-project --auth-type oauth --mode http --defaults
```

What gets created:
- Project directory structure (config/, middleware/, tools/, prompts/, logs/, data/)
- Configuration files (config.json, middleware.json, .env, .env.example)
- Main server entry point (server.py)
- Python project files (pyproject.toml, requirements.txt)
- Documentation (README.md, .gitignore)
- Optional example files (--with-examples flag)

After initialization:
```bash
cd my-project
source .venv/bin/activate  # Virtual environment is auto-created
uv pip install -e .
python server.py
```

Note: By default, init automatically creates a virtual environment (.venv). Use --no-venv to skip this.

### Start Server

```bash
# Start in HTTP mode (default)
mcp-composer --mode http --host 0.0.0.0 --port 9000

# Start in SSE mode
mcp-composer --mode sse --host localhost --port 9000

# Start in STDIO mode
mcp-composer --mode stdio --script-path /path/to/server.py

# Start with OAuth authentication
mcp-composer --mode sse --auth-type oauth --host localhost --port 9000
```

### Help and Version

```bash
# Show help
mcp-composer --help

# Show version
mcp-composer version

# Show information
mcp-composer info

# Show detailed help for specific command
mcp-composer run --help
mcp-composer middleware --help
mcp-composer composer --help
```

## Command Options

### Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--mode` | Server mode: `http`, `sse`, or `stdio` | `stdio` |
| `--host` | Host to bind to (HTTP/SSE mode) | `0.0.0.0` |
| `--port` | Port to run on (HTTP/SSE mode) | `9000` |
| `--id` | Unique ID for MCP instance | `mcp-local` |
| `--endpoint` | Endpoint for HTTP or SSE server running remotely | None |
| `--script-path` | Path to script for stdio mode | None |
| `--directory` | Working directory for uvicorn process | None |
| `--config_path` | Path to JSON config for MCP member servers | None |
| `--auth-type` | Authentication type (oauth) | None |
| `--sse-url` | Langflow compatible URL for remote SSE/HTTP server | None |
| `--remote-auth-type` | Authentication type for remote server | `none` |
| `--client-auth-type` | Authentication type for client | `none` |
| `--disable-composer-tools` | Disable composer tools | `False` |
| `--pass-environment` | Pass through all environment variables | `False` |
| `--env`, `-e` | Environment variables (KEY=VALUE) | [] |
| `--log-level` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| `--timeout` | Timeout in seconds for server operations | None |

### Mode-Specific Options

#### HTTP Mode

```bash
# Basic HTTP server
mcp-composer --mode http --host 0.0.0.0 --port 9000

# With endpoint
mcp-composer --mode http --endpoint http://api.example.com

# With OAuth authentication
mcp-composer --mode http --auth-type oauth --host localhost --port 9000
```

#### SSE Mode

```bash
# Basic SSE server
mcp-composer --mode sse --host localhost --port 9000

# With endpoint
mcp-composer --mode sse --endpoint http://localhost:8001/sse

# With OAuth authentication
mcp-composer --mode sse --auth-type oauth --host localhost --port 9000

# With comprehensive OAuth configuration (W3 IBM OAuth)
mcp-composer --mode http \
  --host localhost \
  --port 9000 \
  --disable-composer-tools \
  --auth_type oauth \
  --env ENABLE_OAUTH True \
  --env OAUTH_HOST localhost \
  --env OAUTH_PORT 9000 \
  --env OAUTH_SERVER_URL http://localhost:9000 \
  --env OAUTH_CALLBACK_PATH http://localhost:9000/auth/idaas/callback \
  --env OAUTH_CLIENT_ID your_client_id \
  --env OAUTH_CLIENT_SECRET your_client_secret \
  --env OAUTH_AUTH_URL https://preprod.login.w3.ibm.com/v1.0/endpoint/default/authorize \
  --env OAUTH_TOKEN_URL https://preprod.login.w3.ibm.com/v1.0/endpoint/default/token \
  --env OAUTH_MCP_SCOPE user \
  --env OAUTH_PROVIDER_SCOPE openid
```

#### STDIO Mode

```bash
# Basic stdio server
mcp-composer --mode stdio --script-path /path/to/server.py

# With custom working directory
mcp-composer --mode stdio --script-path server.py --directory /path/to/working/dir

# With environment variables
mcp-composer --mode stdio --script-path server.py --env DEBUG=true --env LOG_LEVEL=debug
```

## Main Commands

### run - Execute MCP Composer

The main command for running MCP Composer servers with dynamically constructed configuration.

```bash
mcp-composer run [OPTIONS]
```

Examples:

```bash
# HTTP mode with endpoint
mcp-composer run --mode http --endpoint http://api.example.com

# SSE mode with OAuth
mcp-composer run --mode sse --auth-type oauth --host localhost --port 9000

# STDIO mode with script
mcp-composer run --mode stdio --script-path /path/to/server.py --id mcp-news

# With environment variables
mcp-composer run --mode http --env DEBUG=true --env LOG_LEVEL=debug

# With remote server connection
mcp-composer run --mode http --sse-url http://localhost:8001/sse --remote-auth-type oauth
```

### version - Show Version

```bash
mcp-composer version
```

### info - Show Information

```bash
mcp-composer info
```

## Init Command - Initialize Project

### init - Initialize a New MCP Composer Workspace

The init command creates a complete, ready-to-run MCP Composer project with sensible defaults and optional examples.

```bash
mcp-composer init [PROJECT_NAME] [OPTIONS]
```

Key Features:
- Interactive setup with smart defaults
- Multiple setup variants (local development, cloud deployment)
- Automatic environment validation
- Optional example files and configurations
- Idempotent (won't overwrite unless confirmed)
- Colorized, user-friendly output

Options:

| Option | Description | Default |
|--------|-------------|---------|
| `PROJECT_NAME` | Name of the project to initialize | Interactive prompt |
| `--defaults` | Skip interactive prompts and use default values | `False` |
| `--with-examples` | Include example files (tools, middleware, configs) | `False` |
| `--with-venv` / `--no-venv` | Create virtual environment in project | `True` |
| `--adapter` | Setup variant: `local` or `cloud` | Interactive prompt |
| `--port`, `-p` | Default port for HTTP/SSE server | `9000` |
| `--host` | Default host for HTTP/SSE server | `0.0.0.0` |
| `--mode` | Default server mode: `http`, `sse`, or `stdio` | Depends on adapter |
| `--auth-type` | Authentication type: `oauth` or `none` | `none` |
| `--database `| Database type: `sqlite`, `postgres`, or `none` | `none` |
| `--description` | Project description | Generated from name |
| `--directory`, `-d` | Target directory for project | Same as project name |
| `--force`, `-f` | Overwrite existing directory if it exists | `False` |

Examples:

```bash
# Interactive setup (recommended for first-time users)
mcp-composer init my-project

# Quick setup with defaults (non-interactive)
mcp-composer init my-project --defaults

# Local development with examples
mcp-composer init my-local-server --adapter local --mode stdio --with-examples --defaults

# Cloud deployment with HTTP
mcp-composer init my-api-server --adapter cloud --mode http --port 8080 --defaults

# OAuth-enabled server
mcp-composer init secure-server --auth-type oauth --mode http --port 9000 --defaults

# Database-backed server
mcp-composer init data-server --database postgres --mode http --defaults

# Custom directory
mcp-composer init my-project --directory /path/to/custom/location

# Force overwrite existing directory
mcp-composer init my-project --force --defaults

# Skip virtual environment creation
mcp-composer init my-project --no-venv --defaults
```

Project Structure:

After running `init`, you'll get the following structure:

```
my-project/
├── .venv/                  # Virtual environment (auto-created by default)
├── config/                 # Configuration files
│   ├── config.json         # Main MCP Composer configuration
│   └── middleware.json     # Middleware configuration
├── middleware/             # Custom middleware implementations
├── tools/                  # Custom tool implementations
├── prompts/                # Custom prompts
├── logs/                   # Application logs
├── data/                   # Data storage (if database enabled)
├── examples/               # Example files (if --with-examples)
│   ├── tools/              # Example tool implementations
│   ├── middleware/         # Example middleware
│   └── configs/            # Example configurations
├── .env                    # Environment variables
├── .env.example            # Example environment variables
├── .gitignore              # Git ignore file
├── server.py               # Main server entry point
├── pyproject.toml          # Project metadata and dependencies
├── requirements.txt        # Python dependencies
└── README.md               # Project documentation
```

Note: The virtual environment (.venv/) is automatically created unless you use --no-venv.

Interactive Setup Flow:

When running without `--defaults`, you'll be prompted for:

1. Project name: The name of your project
2. Description: A brief description of your project
3. Setup variant: 
   - `local`: For local development (stdio mode default)
   - `cloud`: For cloud deployment (http/sse mode default)
4. Server mode: `stdio`, `http`, or `sse`
5. Port & Host: (Only for http/sse modes)
6. Authentication: `none` or `oauth`
7. Database: `none`, `sqlite`, or `postgres`
8. Include examples: Whether to include example files

Environment Validation:

After creating the project, init automatically validates:

- Python version (3.11+ required)
- uv package manager availability
- git availability (optional)
- Directory write permissions
- Configuration file integrity

Success Message:

After successful initialization, you'll see:

```
✅ Project initialized successfully!

Next steps:
  1. cd my-project
  2. source .venv/bin/activate  # Activate the virtual environment
  3. uv pip install -e .
  4. python server.py
     # Or: mcp-composer run --mode http --config-path config/config.json
     # Visit: http://0.0.0.0:9000

Project Details:
  • Name: my-project
  • Mode: http
  • Adapter: cloud
  • Auth: none
  • Database: none
  • Examples: Yes
  • Virtual Env: ✅ Created

Need help? Run: mcp-composer --help
```

Note: The virtual environment is automatically created and ready to use. Just activate it and install dependencies!

## Middleware Commands

### middleware validate - Validate Configuration

Validates middleware configuration files.

```bash
mcp-composer middleware validate <CONFIG_FILE> [OPTIONS]
```
Options:
- `--ensure-imports`: Verify middleware classes can be imported
- `--format`: Output format (`text`, `json`)
- `--show-middlewares`: Show execution order

Examples:

```bash
# Basic validation
mcp-composer middleware validate middleware-config.json

# With import checking
mcp-composer middleware validate middleware-config.json --ensure-imports

# Show execution order
mcp-composer middleware validate middleware-config.json --show-middlewares
```

### middleware list - List Middlewares

Lists middlewares from configuration files.

```bash
mcp-composer middleware list <CONFIG_FILE> [OPTIONS]
```

Options:
- `--all`: Include disabled middlewares
- `--format`: Output format (text, json)
- `--ensure-imports`: Verify imports

Examples:

```bash
# List enabled middlewares
mcp-composer middleware list middleware-config.json

# List all middlewares
mcp-composer middleware list middleware-config.json --all

# JSON output format
mcp-composer middleware list middleware-config.json --format json
```

### middleware add - Add Middleware

Adds or updates middleware in configuration files.

```bash
mcp-composer middleware add [OPTIONS]
```

Required Options:
- `--config`, `-c`: Configuration file path
- `--name`, `-n`: Middleware name
- `--kind`, `-k`: Python import path (e.g., module.ClassName)

Optional Options:
- `--description`: Middleware description
- `--version`: Middleware version (default: 0.0.0)
- `--mode`: Mode (enabled, disabled, default: enabled)
- `--priority`, -p: Execution priority (default: 100)
- `--applied-hooks`: Comma-separated hooks
- `--include-tools`: Tools to include (default: *)
- `--exclude-tools`: Tools to exclude
- `--config-file`: JSON config file for middleware
- `--update`: Update existing middleware
- `--dry-run`: Show what would be written

Examples:

```bash
# Add simple middleware
mcp-composer middleware add \
  --config middleware-config.json \
  --name Logger \
  --kind mcp_composer.middleware.logging_middleware.LoggingMiddleware

# Add with custom priority and hooks
mcp-composer middleware add \
  --config middleware-config.json \
  --name RateLimiter \
  --kind mcp_composer.middleware.rate_limit_filter.RateLimitingMiddleware \
  --priority 10 \
  --applied-hooks on_call_tool

# Update existing middleware
mcp-composer middleware add \
  --config middleware-config.json \
  --name Logger \
  --kind mcp_composer.middleware.logging_middleware.LoggingMiddleware \
  --update
```

### middleware remove - Remove Middleware

Removes middleware from configuration files.

```bash
mcp-composer middleware remove --config <CONFIG_FILE> --name <MIDDLEWARE_NAME> [OPTIONS]
```

Options:
- `--dry-run`: Show what would be removed

### middleware init - Initialize Configuration

Creates a new middleware configuration file.

```bash
mcp-composer middleware init --config <CONFIG_FILE> [OPTIONS]
```

Options:
- `--force`, `-f`: Overwrite existing file

## Composer Commands

### composer start - Start Server

Starts MCP Composer server with process management options.

```bash
mcp-composer composer start [OPTIONS]
```

Note: Daemon functionality requires the python-daemon dependency. Install it with:
```bash
uv add python-daemon
```

Additional Options (beyond run command):
- `--daemon`, `-D`: Run as daemon process
- `--pid-file`: Path to PID file
- `--log-file`: Path to log file

Examples:

```bash
# Start in HTTP mode
mcp-composer composer start --mode http --endpoint http://api.example.com

# Start in SSE mode with OAuth
mcp-composer composer start --mode sse --auth-type oauth --host localhost --port 9000

# Start as daemon
mcp-composer composer start --mode sse --daemon --pid-file /var/run/mcp-composer.pid

# Start with custom log file
mcp-composer composer start --mode http --daemon --log-file /var/log/mcp-composer.log
```

### composer stop - Stop Server

Stops running MCP Composer daemon.

```bash
mcp-composer composer stop [OPTIONS]
```
Options:
- `--pid-file`: Path to PID file
- `--port`, `-p`: Port number (auto-finds PID file)
- `--force`, `-f`: Force stop

Examples:

```bash
# Stop using PID file
mcp-composer composer stop --pid-file /var/run/mcp-composer.pid

# Stop using port
mcp-composer composer stop --port 9000

# Force stop
mcp-composer composer stop --port 9000 --force
```

### composer status - Check Status

Checks the status of running MCP Composer daemon.

```bash
mcp-composer composer status [OPTIONS]
```

Options:
- `--pid-file`: Path to PID file
- `--port`, `-p`: Port number
- `--format`, `-f`: Output format (text, json)

Examples:

```bash
# Check status using PID file
mcp-composer composer status --pid-file /var/run/mcp-composer.pid

# Check status using port number
mcp-composer composer status --port 9000

# JSON output format
mcp-composer composer status --port 9000 --format json
```

### composer logs - View Logs

Views logs from running MCP Composer daemon.

```bash
mcp-composer composer logs [OPTIONS]
```

Options:
- `--log-file`: Path to log file
- `--port`, `-p`: Port number (auto-finds log file)
- `--lines`, `-n`: Number of lines to show (default: 50)
- `--follow`, `-f`: Follow logs in real-time

Examples:

```bash
# View last 50 lines of logs
mcp-composer composer logs --port 9000

# View last 100 lines of logs
mcp-composer composer logs --port 9000 --lines 100

# Follow logs in real-time
mcp-composer composer logs --port 9000 --follow

# View specific log file
mcp-composer composer logs --log-file /var/log/mcp-composer.log
```

### composer restart - Restart Server

Restarts MCP Composer daemon.

```bash
mcp-composer composer restart [OPTIONS]
```

Options:
- All options from start command
- `--force`, `-f`: Force stop before restarting

Examples:

```bash
# Restart daemon on port 9000
mcp-composer composer restart --port 9000

# Force restart
mcp-composer composer restart --port 9000 --force

# Restart with new configuration
mcp-composer composer restart --mode sse --auth-type oauth --port 9000
```

## Configuration Commands

### Validate Configuration

```bash
# Validate all configurations
mcp-composer --validate-all

# Validate specific components
mcp-composer --validate-env
mcp-composer --validate-servers
mcp-composer --validate-tools
mcp-composer --validate-config
```

### Show Configuration

```bash
# Show current configuration
mcp-composer --show-config

# Show environment variables
mcp-composer --show-env

# Show server configurations
mcp-composer --show-servers

# Show tool configurations
mcp-composer --show-tools
```

## Server Management Commands

### Start Server

```bash
# Start with default settings
mcp-composer start

# Start with custom settings
mcp-composer start --mode http --port 9000 --log-level debug

# Start in background
mcp-composer start --daemon

# Start with PID file
mcp-composer start --pid-file /var/run/mcp-composer.pid
```

### Stop Server

```bash
# Stop server by PID file
mcp-composer stop --pid-file /var/run/mcp-composer.pid

# Stop server by port
mcp-composer stop --port 9000

# Force stop
mcp-composer stop --force
```

### Restart Server

```bash
# Restart server
mcp-composer restart --pid-file /var/run/mcp-composer.pid

# Restart with new configuration
mcp-composer restart --config new-config.json
```

## Health and Status Commands

### Check Health

```bash
# Check server health
mcp-composer health

# Check detailed health
mcp-composer health --detailed

# Check health of specific server
mcp-composer health --server server-id

# Health check with timeout
mcp-composer health --timeout 30
```

### Show Status

```bash
# Show server status
mcp-composer status

# Show member servers status
mcp-composer status --servers

# Show tools status
mcp-composer status --tools

# Show all status information
mcp-composer status --all
```

## Tool Management Commands

### List Tools

```bash
# List all tools
mcp-composer tools list

# List tools by server
mcp-composer tools list --server server-id

# List tools with details
mcp-composer tools list --detailed

# List tools in JSON format
mcp-composer tools list --format json
```

### Manage Tools

```bash
# Enable tools
mcp-composer tools enable tool1 tool2

# Disable tools
mcp-composer tools disable tool1 tool2

# Update tool description
mcp-composer tools update-description tool-name "New description"

# Get tool configuration
mcp-composer tools config tool-name
```

### Add Tools

```bash
# Add tool from file
mcp-composer tools add --file tool-config.json

# Add tool from OpenAPI spec
mcp-composer tools add-openapi --spec openapi.json --auth auth.json

# Add curl tool
mcp-composer tools add-curl --name weather --curl "curl 'https://api.example.com/weather?q={{city}}'"

# Add script tool
mcp-composer tools add-script --name calculate --script "def add(a, b): return a + b"
```

## Server Management Commands

### Register Servers

```bash
# Register server from file
mcp-composer servers register --file server-config.json

# Register HTTP server
mcp-composer servers register --id my-server --type http --endpoint https://api.example.com/mcp

# Register stdio server
mcp-composer servers register --id local-server --type stdio --command python --args server.py

# Register with authentication
mcp-composer servers register --id auth-server --type http --endpoint https://api.example.com/mcp --auth-strategy bearer --auth-token your-token
```

### Manage Servers

```bash
# List servers
mcp-composer servers list

# Activate server
mcp-composer servers activate server-id

# Deactivate server
mcp-composer servers deactivate server-id

# Delete server
mcp-composer servers delete server-id

# Get server configuration
mcp-composer servers config server-id
```

## OAuth Authentication

### Basic OAuth Setup

```bash
# Simple OAuth authentication
mcp-composer --mode http --auth-type oauth --host localhost --port 9000
```

### W3 IBM OAuth Configuration

For IBM W3 OAuth integration, use the following comprehensive configuration:

```bash
mcp-composer --mode http \
  --host localhost \
  --port 9000 \
  --disable-composer-tools \
  --auth_type oauth \
  --env ENABLE_OAUTH=True \
  --env OAUTH_HOST=localhost \
  --env OAUTH_PORT=9000 \
  --env OAUTH_SERVER_URL=http://localhost:9000 \
  --env OAUTH_CALLBACK_PATH=http://localhost:9000/auth/idaas/callback \
  --env OAUTH_CLIENT_ID=your_client_id \
  --env OAUTH_CLIENT_SECRET=your_client_secret \
  --env OAUTH_AUTH_URL=https://preprod.login.w3.ibm.com/v1.0/endpoint/default/authorize \
  --env OAUTH_TOKEN_URL=https://preprod.login.w3.ibm.com/v1.0/endpoint/default/token \
  --env OAUTH_MCP_SCOPE=user \
  --env OAUTH_PROVIDER_SCOPE=openid
```

### OAuth Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ENABLE_OAUTH` | Enable OAuth authentication | `True` |
| `OAUTH_HOST` | OAuth server host | `localhost` |
| `OAUTH_PORT` | OAuth server port | `9000` |
| `OAUTH_SERVER_URL` | Base URL for OAuth server | `http://localhost:9000 `|
| `OAUTH_CALLBACK_PATH` | OAuth callback URL path | `http://localhost:9000/auth/idaas/callback` |
| `OAUTH_CLIENT_ID` | OAuth client ID | `your_client_id` |
| `OAUTH_CLIENT_SECRET` | OAuth client secret | `your_client_secret` |
| `OAUTH_AUTH_URL` | OAuth authorization endpoint | `https://provider.com/oauth/authorize` |
| `OAUTH_TOKEN_URL` | OAuth token endpoint | `https://provider.com/oauth/token` |
| `OAUTH_MCP_SCOPE` | MCP-specific OAuth scope | `user` |
| `OAUTH_PROVIDER_SCOPE` | OAuth provider scope | `openid` |

### OAuth with Composer Commands

```bash
# Start OAuth-enabled server as daemon
mcp-composer composer start --mode http \
  --host localhost \
  --port 9000 \
  --auth-type oauth \
  --daemon \
  --env ENABLE_OAUTH=True \
  --env OAUTH_CLIENT_ID=your_client_id \
  --env OAUTH_CLIENT_SECRET=<yoursecret>

# Check OAuth server status
mcp-composer composer status --port 9000

# View OAuth server logs
mcp-composer composer logs --port 9000 --follow
```

## Logging and Debugging

### Log Management

```bash
# Show logs
mcp-composer logs

# Show recent logs
mcp-composer logs --lines 100

# Show logs with timestamps
mcp-composer logs --timestamps

# Show logs in JSON format
mcp-composer logs --format json

# Follow logs (real-time)
mcp-composer logs --follow

# Show logs for specific level
mcp-composer logs --level error
```

### Debug Mode

```bash
# Start with debug logging
mcp-composer --log-level debug

# Enable debug mode with additional info
mcp-composer --debug --log-level debug

# Debug specific component
mcp-composer --debug-servers --debug-tools
```

## Environment and Configuration

### Environment Management

```bash
# Show environment variables
mcp-composer env show

# Set environment variable
mcp-composer env set KEY value

# Unset environment variable
mcp-composer env unset KEY

# Load environment from file
mcp-composer env load --file .env
```

### Configuration Management

```bash
# Create default configuration
mcp-composer config init

# Validate configuration
mcp-composer config validate

# Show configuration
mcp-composer config show

# Update configuration
mcp-composer config update --key value
```

## Examples

### Development Setup

```bash
# Start development server
mcp-composer --mode http --port 9000 --log-level debug --config config/dev.json

# Start with hot reload
mcp-composer --mode http --port 9000 --reload --log-level debug
```

### Production Setup

```bash
# Start production server
mcp-composer --mode http --port 80 --log-level info --config config/prod.json

# Start as daemon
mcp-composer --mode http --port 80 --daemon --pid-file /var/run/mcp-composer.pid
```

### Testing Setup

```bash
# Start test server
mcp-composer --mode stdio --log-level warning --config config/test.json

# Run tests
mcp-composer test

# Run specific tests
mcp-composer test --test-file test_specific.py
```

### Monitoring Setup

```bash
# Start with monitoring
mcp-composer --mode http --port 9000 --metrics --metrics-port 9090

# Health check
mcp-composer health --timeout 10

# Status check
mcp-composer status --servers --tools
```

### OAuth Setup

```bash
# Start OAuth-enabled server
mcp-composer --mode http \
  --host localhost \
  --port 9000 \
  --disable-composer-tools \
  --auth_type oauth \
  --env ENABLE_OAUTH=True \
  --env OAUTH_CLIENT_ID=<your_client_id> \
  --env OAUTH_CLIENT_SECRET=<yoursecret> \
  --env OAUTH_AUTH_URL=https://preprod.login.w3.ibm.com/v1.0/endpoint/default/authorize \
  --env OAUTH_TOKEN_URL=https://preprod.login.w3.ibm.com/v1.0/endpoint/default/token

# Start OAuth server as daemon
mcp-composer composer start --mode http \
  --host localhost \
  --port 9000 \
  --auth-type oauth \
  --daemon \
  --env ENABLE_OAUTH=True \
  --env OAUTH_CLIENT_ID=<your_client_id> \
  --env OAUTH_CLIENT_SECRET=<your_client_secret>
```

## Troubleshooting

### Common Issues

#### 1. Missing Daemon Dependency

Problem: No module named 'daemon' error when using daemon functionality.

Solution:
```bash
# Install the required dependency
uv add python-daemon

# Then daemon commands will work
mcp-composer composer start --mode sse --daemon --port 9000
```

#### 2. Port Already in Use

Problem: Port is already occupied.

Solution:
```bash
# Check what's using the port
lsof -i :9000

# Use different port
mcp-composer run --port 9001

# Stop existing daemon
mcp-composer composer stop --port 9000 --force
```

#### 3. Permission Issues

Problem: Cannot write PID/log files.

Solution:
```bash
# Use user-writable directories
mcp-composer composer start \
  --daemon \
  --pid-file ~/.mcp-composer.pid \
  --log-file ~/.mcp-composer.log
```

#### 4. OAuth Configuration Issues

Problem: OAuth authentication not working or missing environment variables.

Solution:
```bash
# Verify OAuth environment variables
mcp-composer run --mode http --auth-type oauth --env ENABLE_OAUTH=True --env OAUTH_CLIENT_ID=test

# Check OAuth server logs
mcp-composer composer logs --port 9000 --lines 50

# Test OAuth callback URL
curl -I http://localhost:9000/auth/idaas/callback
```

#### 5. Configuration Validation Errors

Problem: Invalid middleware configuration.

Solution:
```bash
# Validate configuration
mcp-composer middleware validate config.json

# Check JSON syntax
python -m json.tool config.json

# Use dry-run for changes
mcp-composer middleware add --config config.json --dry-run
```

### Debug Commands

```bash
# Enable debug mode
mcp-composer --debug --log-level debug

# Show debug info
mcp-composer --debug-info

# Test connectivity
mcp-composer --test-connectivity

# Check dependencies
mcp-composer --check-deps
```

## Integration Examples

### Systemd Service

Create `/etc/systemd/system/mcp-composer.service`:

```ini
[Unit]
Description=MCP Composer
After=network.target

[Service]
Type=simple
User=mcp-composer
ExecStart=/usr/local/bin/mcp-composer composer start --mode http --port 9000 --daemon --pid-file /var/run/mcp-composer.pid
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Docker Integration

```bash
# Run in Docker
docker run -p 9000:9000 mcp-composer --mode http --port 9000

# Run with custom config
docker run -p 9000:9000 -v $(pwd)/config:/app/config mcp-composer --mode http --port 9000 --config_path /app/config/config.json
```

### CI/CD Integration

```bash
# Validate in CI
mcp-composer --validate-all

# Test in CI
mcp-composer test

# Build for deployment
mcp-composer build --output dist/
```

## Next Steps

- [Configuration Guide](/guide/configuration) - Learn about configuration options
- [API Reference](/api/) - Complete API documentation
- [Examples](/examples/) - See practical examples