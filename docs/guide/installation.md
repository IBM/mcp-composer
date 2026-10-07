# Installation

This guide covers different ways to install and set up MCP Composer.

## Prerequisites

- **Python 3.11+** - MCP Composer requires Python 3.11 or higher
- **[uv](https://docs.astral.sh/uv/)** - Recommended package manager for Python (alternative to pip)

## Method 1: Development Installation (Recommended)

### 1. Clone the Repository

```bash
git clone https://github.com/ibm/mcp-composer.git
cd mcp-composer
```

### 2. Create Virtual Environment

```bash
uv venv
```

### 3. Activate Virtual Environment

**macOS/Linux:**
```bash
source .venv/bin/activate
```

**Windows:**
```bash
.venv\Scripts\activate
```

### 4. Install Dependencies

```bash
# Strict install (recommended for consistency)
uv sync --frozen

# Or install with lock file updates
uv sync

# Or refresh all dependencies
rm uv.lock && uv sync
```

### 5. Verify Installation

```bash
uv run python -c "import mcp_composer; print(mcp_composer.__version__)"
```

## Method 2: Install as Local Dependency

If you want to use MCP Composer in another project:

### 1. Update pyproject.toml

Add this to your project's `pyproject.toml`:

```toml
[tool.hatch.metadata]
allow-direct-references = true

[project]
dependencies = [
    "mcp-composer",
    # ... other dependencies
]

[tool.uv.sources]
mcp-composer = { path = "/path/to/mcp-composer" }
```

### 2. Install

```bash
uv add /path/to/mcp-composer
uv pip install -e /path/to/mcp-composer
```

## Method 3: Install as Tool

### 1. Install as System Tool

```bash
uv tool install -e /absolute/path/to/mcp-composer
```

### 2. Add to PATH

```bash
export PATH="/absolute/path/.local/bin:$PATH"
```

### 3. Verify Installation

```bash
which mcp-composer
mcp-composer --help
```

### 4. Uninstall (if needed)

```bash
uv tool uninstall mcp-composer
```

## Method 4: Docker Installation

### 1. Build Docker Image

```bash
docker build -t mcp-composer .
```

### 2. Run Container

```bash
docker run -p 9000:9000 mcp-composer
```

## Configuration

### Environment Setup

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Configure your settings in `.env`:

```env
# Server Configuration
MCP_SERVER_CONFIG_PATH=example/member_servers.json
MCP_TOOL_CONFIG_PATH=config/tools.json

# Database Configuration
DATABASE_TYPE=local_file
DATABASE_PATH=data/mcp_composer.db

# Logging
LOG_LEVEL=INFO
```

### Directory Structure

After installation, your project should look like:

```
mcp-composer/
├── src/
│   ├── .env                    # Environment configuration
│   └── mcp_composer/          # Main package
├── example/
│   ├── member_servers.json    # Sample member servers
│   └── unified_config.json    # Sample unified config
├── config/
│   └── tools.json             # Tool configurations
├── data/                      # Database files
└── .venv/                     # Virtual environment
```

## Troubleshooting

### Common Issues

1. **Python Version Error**
   ```bash
   # Check Python version
   python --version
   
   # Should be 3.11 or higher
   ```

2. **uv Not Found**
   ```bash
   # Install uv
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Import Error**
   ```bash
   # Make sure you're in the virtual environment
   source .venv/bin/activate
   
   # Reinstall dependencies
   uv sync --frozen
   ```

4. **Permission Errors**
   ```bash
   # Fix permissions
   chmod +x .venv/bin/activate
   ```

### Getting Help

- Review [GitHub Issues](https://github.com/ibm/mcp-composer/issues)
- Consult the [API Documentation](/api/)

## Next Steps

- [Quick Start Guide](/guide/quick-start) - Get up and running
- [Configuration Guide](/guide/configuration) - Learn about configuration options
- [CLI Usage](/guide/cli) - Understand command-line interface 