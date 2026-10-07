---
layout: home
hero:
  name: MCP Composer
  text: FastMCP-based MCP Server Orchestrator
  tagline: Manage multiple MCP servers and tools with dynamic registration, authentication, and unified interface
  actions:
    - theme: brand
      text: Get Started
      link: /guide/
    - theme: alt
      text: View on GitHub
      link: https://github.com/ibm/mcp-composer
features:
  - icon: 🚀
    title: Dynamic Tool Registration
    details: Register or remove tools at runtime using structured JSON configurations. Support for OpenAPI, GraphQL, CLI-based tools, and nested MCP servers.
  - icon: 🔐
    title: Multi-Auth Support
    details: Handle multiple authentication strategies including OAuth, Bearer tokens, Basic auth, and custom authentication flows.
  - icon: 🔄
    title: Unified Interface
    details: Expose all tools across registered servers through a single, unified MCP-compliant interface with automatic request forwarding.
  - icon: 🏥
    title: Health Monitoring
    details: Built-in health monitoring and status tracking for all member servers with automatic failover and recovery.
  - icon: 🛠️
    title: CLI & API
    details: Launch via CLI or integrate via API. Support for both HTTP and stdio modes with flexible configuration options.
  - icon: 🤖
    title: MCP Clients
    details: Connect any MCP client, including MCP Inspector, over stdio, HTTP, or SSE. 