# MCP Inspector Demo

This guide shows you how to use MCP Inspector to test and interact with MCP Composer.

## Overview

MCP Inspector is a web-based tool for testing MCP servers. It provides a user-friendly interface to:

- Connect to MCP servers
- List available tools
- Invoke tools with parameters
- View responses and errors
- Debug MCP interactions

## Prerequisites

1. **MCP Composer Running**: Make sure MCP Composer is running in HTTP mode
2. **Node.js**: Required to run MCP Inspector
3. **Browser**: Modern web browser (Chrome, Firefox, Safari, Edge)

## Step 1: Start MCP Composer

### Option A: Using CLI

```bash
# Start MCP Composer in HTTP mode
mcp-composer --mode http --port 9000
```

### Option B: Using Python Script

```bash
# Navigate to src directory
cd src

# Run the test composer
uv run test/test_composer.py
```

### Verify MCP Composer is Running

```bash
# Check health endpoint
curl http://localhost:9000/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "0.1.0"
}
```

## Step 2: Install MCP Inspector

### Install via npm

```bash
# Install latest version
npx @modelcontextprotocol/inspector

# Or install specific version
npx @modelcontextprotocol/inspector@0.14.3

# Or install globally
npm install -g @modelcontextprotocol/inspector
```

### Alternative: Clone Repository

```bash
git clone https://github.com/modelcontextprotocol/inspector.git
cd inspector
npm install
npm start
```

## Step 3: Launch MCP Inspector

### Using npx

```bash
npx @modelcontextprotocol/inspector
```

### Using Global Installation

```bash
mcp-inspector
```

### Manual Start

```bash
cd inspector
npm start
```

## Step 4: Connect to MCP Composer

### 1. Open MCP Inspector

Navigate to the URL shown in the terminal (usually `http://localhost:6274`)

### 2. Configure Connection

Fill in the connection details:

- **Transport Type**: `http`
- **URL**: `http://localhost:9000/mcp`
- **Session Token**: Leave empty (or use token if provided)

### 3. Connect

Click the **Connect** button to establish connection with MCP Composer.

## Step 5: Explore Available Tools

### List Tools

1. Go to the **Tools** tab
2. Click **List Tools** to see all available tools
3. You should see MCP Composer's built-in tools:
   - `register_mcp_server`
   - `delete_mcp_server`
   - `member_health`
   - `activate_mcp_server`
   - `deactivate_mcp_server`
   - `list_member_servers`
   - `get_tool_config_by_name`
   - `get_tool_config_by_server`
   - `disable_tools`
   - `enable_tools`
   - `update_tool_description`
   - `add_tools`
   - `add_tools_from_openapi`
   - `add_prompts`
   - `get_all_prompts`

### Tool Details

Click on any tool to see its:
- Description
- Input schema
- Required parameters
- Example usage

## Step 6: Register a Test Server

### Example: Register Stock Info Server

1. **Select Tool**: Choose `register_mcp_server`
2. **Fill Parameters**:

```json
{
  "id": "mcp-stock-info",
  "type": "http",
  "endpoint": "https://mcp-stock-info.1vgzmntiwjzl.eu-es.codeengine.appdomain.cloud/mcp"
}
```

3. **Execute**: Click **Call Tool**

### Expected Response

```json
{
  "content": [
    {
      "type": "text",
      "text": "Server registered successfully"
    }
  ]
}
```

## Step 7: List Tools Again

### Refresh Tool List

1. **Clear Tools**: Click **Clear Tools** to refresh the list
2. **List Tools**: Click **List Tools** again
3. **New Tools**: You should now see tools from the registered server:
   - `get_stock_price`
   - `get_stock_info`
   - `search_stocks`

## Step 8: Test Registered Tools

### Example: Get Stock Price

1. **Select Tool**: Choose `get_stock_price`
2. **Fill Parameters**:

```json
{
  "symbol": "AAPL"
}
```

3. **Execute**: Click **Call Tool**

### Expected Response

```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"symbol\":\"AAPL\",\"price\":150.25,\"currency\":\"USD\",\"timestamp\":\"2024-01-01T12:00:00Z\"}"
    }
  ]
}
```

## Step 9: Advanced Testing

### Test Error Handling

Try calling a tool with invalid parameters:

```json
{
  "symbol": "INVALID_SYMBOL"
}
```

### Test Multiple Tools

1. **Get Stock Info**:
   ```json
   {
     "symbol": "GOOGL"
   }
   ```

2. **Search Stocks**:
   ```json
   {
     "query": "tech"
   }
   ```

## Step 10: Monitor Server Health

### Check Member Health

1. **Select Tool**: Choose `member_health`
2. **Execute**: Click **Call Tool** (no parameters needed)

### Expected Response

```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"mcp-stock-info\":{\"status\":\"healthy\",\"last_check\":\"2024-01-01T12:00:00Z\",\"response_time\":150}}"
    }
  ]
}
```

## Step 11: Manage Servers

### List Member Servers

1. **Select Tool**: Choose `list_member_servers`
2. **Execute**: Click **Call Tool**

### Deactivate Server

1. **Select Tool**: Choose `deactivate_mcp_server`
2. **Fill Parameters**:
   ```json
   {
     "server_id": "mcp-stock-info"
   }
   ```
3. **Execute**: Click **Call Tool**

### Reactivate Server

1. **Select Tool**: Choose `activate_mcp_server`
2. **Fill Parameters**:
   ```json
   {
     "server_id": "mcp-stock-info"
   }
   ```
3. **Execute**: Click **Call Tool**

## Step 12: Add Custom Tools

### Add Curl Tool

1. **Select Tool**: Choose `add_tools`
2. **Fill Parameters**:

```json
{
  "tools": [
    {
      "name": "weather",
      "tool_type": "curl",
      "curl_config": {
        "value": "curl 'https://api.openweathermap.org/data/2.5/weather?q={{city}}&appid=YOUR_API_KEY'"
      },
      "description": "Get weather information for a city",
      "permission": {
        "user": "read"
      }
    }
  ]
}
```

3. **Execute**: Click **Call Tool**

### Test Custom Tool

1. **List Tools**: Refresh the tool list
2. **Select Tool**: Choose the new `weather` tool
3. **Fill Parameters**:
   ```json
   {
     "city": "New York"
   }
   ```
4. **Execute**: Click **Call Tool**

## Troubleshooting

### Common Issues

#### 1. Connection Failed

**Symptoms**: Cannot connect to MCP Composer

**Solutions**:
```bash
# Check if MCP Composer is running
curl http://localhost:9000/health

# Check port availability
netstat -an | grep 9000

# Restart MCP Composer
mcp-composer --mode http --port 9000
```

#### 2. Tools Not Loading

**Symptoms**: No tools appear after registration

**Solutions**:
- Clear tools and list again
- Check server health
- Verify server configuration
- Check logs for errors

#### 3. Tool Execution Fails

**Symptoms**: Tool calls return errors

**Solutions**:
- Check tool parameters
- Verify server connectivity
- Check authentication
- Review error messages

#### 4. MCP Inspector Not Starting

**Symptoms**: Cannot launch MCP Inspector

**Solutions**:
```bash
# Check Node.js version
node --version

# Clear npm cache
npm cache clean --force

# Reinstall MCP Inspector
npm uninstall -g @modelcontextprotocol/inspector
npm install -g @modelcontextprotocol/inspector
```

#### 5. 400 Bad Request When Registering GitHub MCP Server

**Symptoms**: `register_mcp_server` fails with `400 Bad Request` when called through MCP Inspector.

**Root Cause**: MCP Inspector automatically injects an extra `Authorization` header on outbound requests when you also provide a bearer token in the payload. MCP Composer forwards both headers to the GitHub MCP server, which rejects the duplicated credential.

**Solutions**:
- Clear the optional `Authorization` field in MCP Inspector before calling `register_mcp_server`.
- If authentication is required, supply credentials exclusively through MCP Composer’s configuration rather than the Inspector UI.
- As a temporary workaround, invoke `register_mcp_server` via CLI or `uv run` so that only the intended headers are sent.

### Debug Mode

Enable debug logging in MCP Composer:

```bash
# Start with debug logging
mcp-composer --mode http --port 9000 --log-level debug
```

### Log Analysis

Check MCP Composer logs for errors:

```bash
# View logs
tail -f logs/mcp_composer.log

# Search for errors
grep ERROR logs/mcp_composer.log
```

## Best Practices

### Testing Workflow

1. **Start Simple**: Begin with basic tools
2. **Test Incrementally**: Add one server at a time
3. **Verify Health**: Check server status regularly
4. **Document Issues**: Note any problems encountered
5. **Clean Up**: Remove test servers when done

### Security Considerations

1. **Use Test Data**: Avoid production credentials
2. **Limit Access**: Use localhost for testing
3. **Monitor Logs**: Watch for suspicious activity
4. **Clean Environment**: Remove test configurations

### Performance Testing

1. **Load Testing**: Test with multiple concurrent requests
2. **Response Times**: Monitor tool execution times
3. **Resource Usage**: Check memory and CPU usage
4. **Error Rates**: Monitor failure rates

## Next Steps

- [API Reference](/api/) - Complete API documentation
- [Configuration Guide](/guide/configuration) - Advanced configuration options
- [Quick Start Guide](/guide/quick-start) - Get up and running 