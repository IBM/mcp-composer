# CLI Usage

This guide covers the command-line interface (CLI) for MCP Composer.

## Overview

MCP Composer provides a powerful CLI that allows you to:

- Start the server in different modes
- Configure server settings
- Validate configurations
- Manage tools and servers
- Monitor health and status

## Basic Usage

### Start Server

```bash
# Start in HTTP mode (default)
mcp-composer

# Start in stdio mode
mcp-composer --mode stdio

# Start with custom port
mcp-composer --port 8080

# Start with custom host
mcp-composer --host 127.0.0.1 --port 9000
```

### Help and Version

```bash
# Show help
mcp-composer --help

# Show version
mcp-composer --version

# Show detailed help for specific command
mcp-composer start --help
```

## Command Options

### Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--mode` | Server mode: `http` or `stdio` | `http` |
| `--host` | Host to bind to (HTTP mode) | `0.0.0.0` |
| `--port` | Port to run on (HTTP mode) | `9000` |
| `--path` | URL path to mount MCP Composer | `/mcp` |
| `--log-level` | Log level: `debug`, `info`, `warning`, `error` | `info` |
| `--config` | Path to configuration file | `config/config.json` |
| `--env-file` | Path to environment file | `src/.env` |

### Mode-Specific Options

#### HTTP Mode

```bash
# Basic HTTP server
mcp-composer --mode http --port 9000

# With custom host and path
mcp-composer --mode http --host localhost --port 8080 --path /api/mcp

# With SSL (if configured)
mcp-composer --mode http --port 443 --ssl-cert cert.pem --ssl-key key.pem
```

#### Stdio Mode

```bash
# Basic stdio server
mcp-composer --mode stdio

# With custom working directory
mcp-composer --mode stdio --workdir /path/to/working/dir

# With environment variables
mcp-composer --mode stdio --env-file /path/to/env
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

## Troubleshooting

### Common Issues

#### Port Already in Use

```bash
# Check what's using the port
lsof -i :9000

# Kill process using port
kill -9 $(lsof -t -i:9000)

# Use different port
mcp-composer --port 9001
```

#### Permission Denied

```bash
# Check file permissions
ls -la config/

# Fix permissions
chmod 644 config/*.json
chmod 755 mcp-composer
```

#### Configuration Errors

```bash
# Validate configuration
mcp-composer --validate-all

# Show configuration
mcp-composer --show-config

# Check environment
mcp-composer --show-env
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
ExecStart=/usr/local/bin/mcp-composer --mode http --port 9000 --daemon --pid-file /var/run/mcp-composer.pid
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
docker run -p 9000:9000 -v $(pwd)/config:/app/config mcp-composer --mode http --port 9000 --config /app/config/config.json
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