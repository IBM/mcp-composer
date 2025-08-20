# MCP Composer Release Roadmap – August 2025

## Release Name: MCP Composer v0.1 AUG"
**Target Date:** 2025-08-31  
**Release Type:** Major feature release with multiple parallel tracks.

---

### Release Goals
- Enable Features e.g. Multi-Teanancy , Middleware as plaugins
- Deploy the mcp-composer on solis platform
- Release pypi for mcp-composer
- Release functionality for langlfow 1.6 relelase

---

### Included Features

1. **Middleware Pattern Updates**  
   - Added feature to add middleware as plugin from configuration
   - Added semantic similarity checks for prompt filtering, pii reduction, rate limit.

2. **Policy-Aware RBAC Enforcement**  
   - HashiCorp Vault HCL-based per-tool access control.  
   - 

3. **Multi-Tenant MCP Server Support**  
   - Tool naming convention: `tenantid_serverid_toolname`.  
   - Tenant-aware resource search with prefix filtering.

4. **Plugin System for Middleware**  
   - `composer add-plugin <repo>` CLI for installing plugins.  
   - Dynamic middleware loading from TOML config.

5. **Langflow Integration**
   - Direct MCP Composer connector node in Langflow.  
   - Load MCP server tools as Langflow components.  
   - Execute Langflow workflows with MCP tool calls.  
   - Support different authentication pattern for mcp server .
---

### Parallel Workstreams

| Workstream | Owner | Dependencies | Status |
|------------|-------|--------------|--------|
| Security Middleware | | Harshicorp team  | In Progress |
| RBAC Middleware | Access Control Team | Vault dev setup | Completed |
| Multi-Tenancy | Core MCP Composer Team | Tool routing updates | Planned |
| Plugin Loader | Developer Experience Team | MiddlewareManager update | Planned |
| Deployment on Solis platform | CI/CD Team | None | Completed |
| PyPI Release | Roy | IBM Open source Legal team | In Progress |
| Langflow Integration | Langflow team | IBM Open source Legal team, PyPi Release | In Progress |

---

# MCP Composer Release Roadmap – September 2025

## Release Name: MCP Composer v0.2 SEPT"
**Target Date:** 2025-09-30  
**Release Type:** Major feature release with multiple parallel tracks.

---

### Release Goals
- Release functionality for langlfow 1.7 relelase
- Deploy on Sidekick 



### Included Features

1. **Langflow Integration**
   - Add MCP_Composer component or Update the existing MCP conenction componet to enable 
        - Add dynamic tool, server on run time, add tool from open api spec , add middleware from command line
   - Enable  Langflow to perform mcp server orchestration.     
   - Enable Langflow with carbon chat for Solis chat ui 

2. **Deploy on Sidekick platform**
   - Enable agent and mcp server from non MCSP products. 
   - Orchestrate  agents and mcp server for Sidekick   