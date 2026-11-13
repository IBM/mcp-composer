# Example Tool Audit Analysis

This document provides a concrete example of analyzing the `tools.json` file to demonstrate the audit process. It uses [`../examples/sample_tools.json`](../examples/sample_tools.json) — a small made-up catalog with two fictional servers and ten tools designed to illustrate common issue categories.

## CRITICAL: Accurate Tool Counting

**Always count tools programmatically, never estimate:**

```python
import json

with open('tools.json', 'r') as f:
    data = json.load(f)

total_entries = 0
error_tools = 0
real_tools = 0

for server, tools in data.get('active', {}).items():
    server_count = len(tools)
    total_entries += server_count

    # Check if this is an ERROR placeholder
    if tools and (tools[0].get('name', '').startswith('ERROR') or
                  'HTTP Error' in tools[0].get('description', '')):
        error_tools += 1
        print(f'{server}: ERROR (auth/connectivity issue)')
    else:
        real_tools += server_count
        print(f'{server}: {server_count} tools')

print(f'\nTotal entries: {total_entries}')
print(f'ERROR placeholders: {error_tools}')
print(f'Real tools: {real_tools}')
```

**Output for `examples/sample_tools.json`:**
```
mcp-inventory: 5 tools
mcp-billing: 5 tools

Total entries: 10
ERROR placeholders: 0
Real tools: 10
```

## Sample Data Structure

```json
{
  "active": {
    "mcp-inventory": [
      {
        "name": "get_item",
        "description": "Retrieve a single inventory item by its SKU, including quantity on hand and warehouse location."
      },
      {
        "name": "get_user",
        "description": "Get user"
      }
    ],
    "mcp-billing": [
      {
        "name": "get_user",
        "description": "Get the billing profile for a customer, including payment method and billing address."
      },
      {
        "name": "do_action",
        "description": "Perform action"
      }
    ]
  },
  "deactivated": ["mcp-legacy-reports"]
}
```

## Example Issues Found

### 1. Critical: Exact Duplicate Names (Cross-Server)

**Issue**: `get_user` appears in both `mcp-inventory` and `mcp-billing` with different descriptions.

**Analysis**:
- **Name**: `get_user` (appears in 2 servers)
- **Servers**: `mcp-inventory`, `mcp-billing`
- **Descriptions**: differ — one is vague ("Get user"), the other describes billing profile
- **Problem**: Agent cannot determine which server's `get_user` to call
- **Impact**: Wrong data returned; billing queries may hit the inventory user lookup

**Failure Scenario**:
```
User Query: "Show me the billing details for customer 42"
Available Tools:
  1. get_user (mcp-inventory) - "Get user"
  2. get_user (mcp-billing)   - "Get the billing profile for a customer..."

Agent Behavior: May select mcp-inventory version due to the vague description
               matching broadly, or may ask for clarification.

Impact: Wrong data returned, user confusion, wasted API call
```

**Recommendation**:
```
Rename each tool to include the server context:

Before: get_user (mcp-inventory) - "Get user"
After:  get_inventory_user - "Retrieve a warehouse operator by user ID,
        including assigned warehouses and role."

Before: get_user (mcp-billing) - "Get the billing profile for a customer..."
After:  get_billing_customer - "Get the billing profile for a customer,
        including payment method and billing address."
```

### 2. Critical: Vague Descriptions

**Issue**: Two tools have extremely short, uninformative descriptions.

**Examples**:

| Tool Name | Server | Current Description | Length | Quality Score | Issues |
|-----------|--------|---------------------|--------|---------------|--------|
| `get_user` | `mcp-inventory` | "Get user" | 8 chars | 1/10 | No context: which user? what data? |
| `do_action` | `mcp-billing` | "Perform action" | 14 chars | 1/10 | Generic verb+noun, no meaning |

**Failure Scenario for `do_action`**:
```
User Query: "Apply a refund for invoice INV-2024-001"

Available Tools:
  - do_action (mcp-billing) - "Perform action"

Agent Behavior:
  - May skip do_action because the description gives no hint it handles refunds
  - May report "no tool available" even though the tool exists
  - May try do_action blindly and pass incorrect parameters

Impact: Task not completed, poor user experience
```

**Recommendations**:

```
Before: get_user (mcp-inventory) - "Get user"
After:  get_inventory_user - "Retrieve a warehouse operator by user ID,
        including assigned warehouses and role."

Before: do_action (mcp-billing) - "Perform action"
After:  issue_refund - "Issue a full or partial refund for a paid invoice
        by invoice ID."
```

### 3. High Priority: Overlapping Descriptions

**Issue**: `list_items` and `search_items` in `mcp-inventory` have near-identical descriptions.

**Current**:
```json
{
  "name": "list_items",
  "description": "List inventory items, optionally filtered by warehouse or category."
},
{
  "name": "search_items",
  "description": "List inventory items, optionally filtered by warehouse, category, or keyword."
}
```

**Problems**:
- `search_items` is a strict superset of `list_items`
- Agent cannot determine when to prefer one over the other
- Descriptions both start with the same phrase

**Recommendation**:
```
Option A — Remove list_items (search_items covers all cases):
  Keep: search_items
    Description: "Search inventory items by warehouse, category, or keyword.
                  Returns all items when no filters are supplied."

Option B — Keep both with clearer differentiation:
  list_items:   "Browse all inventory items grouped by category or warehouse.
                 Use when the user wants to explore without a specific keyword."
  search_items: "Search inventory items by keyword across name, SKU, and tags.
                 Use when the user has a specific term to look up."
```

### 4. High Priority: Similar Names

**Issue**: `get_user` and `get_users` in `mcp-billing` differ by one character.

| Tool Name | Current Description | Issue |
|-----------|---------------------|-------|
| `get_user` | "Get the billing profile for a customer..." | Singular |
| `get_users` | "List all customers with their billing profiles..." | Plural |

**Recommendation**:
```
Rename to make the singular/plural intent unmistakable:

Before: get_user  → After: get_billing_customer
Before: get_users → After: list_billing_customers
```

## Statistical Summary

### Overall Metrics
- **Total Tools Analyzed**: 10 (5 per server)
- **Tools with Issues**: 6
- **Critical Issues**: 3 (1 cross-server name collision, 2 vague descriptions)
- **High Priority Issues**: 2 (1 overlapping description pair, 1 near-identical name pair)
- **Medium Priority Issues**: 0
- **Low Priority Issues**: 0

### Description Length Distribution
```
< 10 chars:  1 tool (10%)  ❌ Too short
10-20 chars: 1 tool (10%)  ⚠️  Minimal
20-40 chars: 0 tools (0%)
> 40 chars:  8 tools (80%) ✓✓ Good
```

### Quality Score Distribution
```
0-2:  2 tools (20%) ❌ Poor
3-5:  0 tools (0%)
6-7:  0 tools (0%)
8-10: 8 tools (80%) ✓✓ Good
```

## Prioritized Action Plan

### Week 1: Critical Fixes
1. [ ] Rename both `get_user` tools to server-scoped names
2. [ ] Rewrite `get_user` (inventory) description — currently 8 characters
3. [ ] Rewrite `do_action` description — currently 14 characters

### Week 2: High Priority Improvements
1. [ ] Clarify `list_items` vs `search_items` (or remove `list_items`)
2. [ ] Rename `get_users` to `list_billing_customers` for consistency

## Validation Rules Applied

### Automated Checks
```yaml
✅ No duplicate names within same server: PASSED
✅ No duplicate names across servers:     FAILED (get_user)
✅ Description length > 20 characters:   FAILED (get_user, do_action)
✅ Description differs from name:         FAILED (get_user → "Get user")
✅ No identical descriptions:             PASSED
✅ No special characters in names:        PASSED
```

### Quality Metrics
```
Overall Health Score: 5/10

Breakdown:
- Naming Quality:       6/10  (one cross-server collision, one near-identical pair)
- Description Quality:  5/10  (two critically vague; rest are good)
- Uniqueness:           7/10  (collision but no within-server duplicates)
- Consistency:          8/10  (mostly verb_noun pattern)
```

## Lessons Learned

1. **Cross-server collisions are critical**: Two servers naming their user lookup `get_user` forces the agent to guess
2. **Description length matters**: 8-character descriptions give the agent nothing to work with
3. **Near-duplicates confuse selection**: `list_items` / `search_items` overlap makes both less useful
4. **Good tools set the bar**: `get_item`, `update_stock`, `get_invoice`, `list_invoices` show what clear definitions look like

## Next Steps

1. Fix critical naming collision (`get_user` in both servers)
2. Rewrite vague descriptions (`get_user` inventory, `do_action`)
3. Resolve `list_items` / `search_items` overlap
4. Standardize naming convention for single vs. multiple resources
