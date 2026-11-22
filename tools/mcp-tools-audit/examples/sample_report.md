# Tool Definition Audit Report (Sample)

This is an illustrative example of the kind of report the `tool-audit` Bob skill produces. It was
written by hand for [`sample_tools.json`](sample_tools.json), a small made-up catalog with two
fictional servers. The issues in the catalog were planted on purpose so each audit category has
something to find. Your own report will differ in wording. The full report structure is in
[`../bob-skills/report-template.md`](../bob-skills/report-template.md).

**Tools analyzed**: 10 | **Active servers**: 2 | **Deactivated servers**: 1

---

## Executive Summary

### Key Findings

- **Critical issues**: 3
  - 1 exact name duplicate with different functionality (`get_user`)
  - 2 critically vague descriptions (under 15 characters)
- **High priority issues**: 2
  - 1 pair of near-identical names (`get_user` / `get_users`)
  - 1 pair of overlapping descriptions (`list_items` / `search_items`)
- **Medium and low priority issues**: 0

### Overall Health Score

**5/10**: Most tools are well described, but one name collision and two vague tools are enough to
cause wrong tool calls.

### Top Recommendations

1. Rename the two `get_user` tools so each name says which system it belongs to.
2. Rewrite `get_user` (inventory) and `do_action` (billing) so the description says what they do.
3. Merge `list_items` and `search_items`, or state in each description when to use which.

---

## 1. Tool Inventory

| Metric | Value |
|--------|-------|
| Total tools | 10 |
| Active servers | 2 |
| Deactivated servers | 1 (`mcp-legacy-reports`, not audited) |
| Average tools per server | 5 |
| Tools with issues | 6 |
| Issue-free tools | 4 |

| Server | Tools | Tools with issues |
|--------|-------|-------------------|
| `mcp-inventory` | 5 | 3 (`list_items`, `search_items`, `get_user`) |
| `mcp-billing` | 5 | 3 (`get_user`, `get_users`, `do_action`) |

---

## 2. Naming Collisions

### Critical: exact duplicates

| Tool name | Servers | Impact | Recommendation |
|-----------|---------|--------|----------------|
| `get_user` | `mcp-inventory`, `mcp-billing` | The agent cannot tell which one to call | `get_inventory_user`, `get_billing_customer` |

**Example failure**

```
User query: "Show me the billing details for customer 42"
Problem:    two tools are named get_user, and one of them is described only as "Get user"
Result:     the agent may call the inventory version and return the wrong data
```

### High priority: similar names

| Tool 1 | Tool 2 | Difference | Server | Recommendation |
|--------|--------|------------|--------|----------------|
| `get_user` | `get_users` | 1 character | `mcp-billing` | `get_billing_customer` (one) and `list_billing_customers` (many) |

---

## 3. Description Overlaps

### High priority: highly similar descriptions

| Tool 1 | Tool 2 | Server | Recommendation |
|--------|--------|--------|----------------|
| `list_items`: "List inventory items, optionally filtered by warehouse or category." | `search_items`: "List inventory items, optionally filtered by warehouse, category, or keyword." | `mcp-inventory` | `search_items` is a superset. Remove `list_items`, or say "Use `list_items` for browsing and `search_items` when the user gives a keyword". |

---

## 4. Ambiguous Descriptions

### Critical: under 15 characters

| Tool | Server | Description | Recommendation |
|------|--------|-------------|----------------|
| `get_user` | `mcp-inventory` | "Get user" (8 characters) | State which user, what is returned, and how it is looked up. For example: "Retrieve a warehouse operator by user ID, including assigned warehouses and role." |
| `do_action` | `mcp-billing` | "Perform action" (14 characters) | Replace the generic name and describe the action. For example: `issue_refund`: "Issue a full or partial refund for a paid invoice by invoice ID." |

---

## 5. What Good Looks Like

These four tools passed every check. They state what is returned, how it is looked up, and what the
optional parameters do.

- `get_item`
- `update_stock`
- `get_invoice`
- `list_invoices`

---

## 6. Prevention Guidelines

- Prefix or qualify names that could exist in another system (`get_billing_customer`, not `get_user`).
- Use a distinct verb for single versus many (`get_x` versus `list_xs`).
- Write at least 40 characters. Say what is returned and how the target is identified.
- Before adding a tool, search the existing catalog for a tool with the same name or a near-identical
  description.

---

## Try it yourself

With the `tool-audit` skill installed (see [`../INSTALL.md`](../INSTALL.md)), open Bob in Agent mode
and ask: "Audit the tool definitions in examples/sample_tools.json". Compare the result with this
report.
