# Tool Definition Audit Report

**Date**: [Date]  
**Auditor**: [Name/Tool]  
**Tools Analyzed**: [Total Count]  
**Servers/Products**: [Count]

---

## Executive Summary

### Key Findings
- **Critical Issues**: [Count] - Exact name duplicates with different functionality
- **High Priority Issues**: [Count] - Similar names with overlapping descriptions
- **Medium Priority Issues**: [Count] - Vague descriptions or naming similarities
- **Low Priority Issues**: [Count] - Style inconsistencies

### Overall Health Score
[Score]/10 - [Brief assessment of tool catalog quality]

### Top Recommendations
1. [Most important recommendation]
2. [Second most important]
3. [Third most important]

---

## 1. Tool Inventory

### Summary Statistics
| Metric | Value |
|--------|-------|
| Total Tools | [count] |
| Total Servers | [count] |
| Average Tools per Server | [count] |
| Tools with Issues | [count] |
| Issue-Free Tools | [count] |

### Tools by Server
| Server Name | Tool Count | Issues Found |
|-------------|------------|--------------|
| [server-1] | [count] | [count] |
| [server-2] | [count] | [count] |

---

## 2. Naming Collisions

### Critical: Exact Duplicates

**Issue**: Multiple servers define tools with identical names but different functionality.

| Tool Name | Servers | Impact | Recommendation |
|-----------|---------|--------|----------------|
| `get_user` | mcp-inventory, mcp-billing | Agent cannot tell which user context to use | Rename to `get_inventory_user`, `get_billing_customer` |
| `do_action` | mcp-billing | Name gives no clue about function | Rename to something specific, e.g. `issue_refund` |

**Example Failure Scenario**:
```
User Query: "Get the billing details for customer 42"
Problem: Two tools named "get_user" exist in different servers
Result: Agent may call the inventory version and return the wrong data
Impact: Wrong information returned, user confusion
```

### High Priority: Similar Names

**Issue**: Tools with very similar names that may be confused.

| Tool Name 1 | Tool Name 2 | Similarity | Servers | Recommendation |
|-------------|-------------|------------|---------|----------------|
| `get_user` | `get_users` | 1 char diff | mcp-billing | Clarify: `get_billing_customer`, `list_billing_customers` |
| `list_items` | `search_items` | Nearly identical descriptions | mcp-inventory | State when to use each, or merge into `search_items` |

---

## 3. Description Overlaps

### Critical: Identical Descriptions

**Issue**: Different tools with identical descriptions.

| Description | Tool Names | Servers | Problem |
|-------------|------------|---------|---------|
| "Get user" | `get_user` | mcp-inventory | Vague — no context about which user or what data |
| "Perform action" | `do_action` | mcp-billing | Gives no hint about what the action does |

**Recommended Rewrites**:
```
Before: "Get user" (mcp-inventory)
After:  "Retrieve a warehouse operator by user ID, including
         assigned warehouses and role."

Before: "Perform action" (mcp-billing)
After:  "Issue a full or partial refund for a paid invoice by
         invoice ID."
```

### High Priority: Highly Similar Descriptions (>80% similarity)

| Tool 1 | Tool 2 | Description 1 | Description 2 | Similarity |
|--------|--------|---------------|---------------|------------|
| `list_items` | `search_items` | "List inventory items, optionally filtered by warehouse or category." | "List inventory items, optionally filtered by warehouse, category, or keyword." | 90% |

---

## 4. Ambiguous Descriptions

### Vague or Generic Descriptions

**Issue**: Descriptions that don't provide enough context or specificity.

| Tool Name | Current Description | Quality Score | Issues | Recommended Description |
|-----------|---------------------|---------------|--------|------------------------|
| `get_user` | "Get user" | 1/10 | Too short, no context | "Retrieve a warehouse operator by user ID, including assigned warehouses and role." |
| `do_action` | "Perform action" | 1/10 | Generic, no meaning | "Issue a full or partial refund for a paid invoice by invoice ID." |

### Too Short (<20 characters)

| Tool Name | Description | Length | Recommendation |
|-----------|-------------|--------|----------------|
| `get_user` | "Get user" | 8 chars | Expand to explain which user and what data is returned |
| `do_action` | "Perform action" | 14 chars | Replace generic name and description with specific action |

---

## 5. Issue Categories by Severity

### Critical Issues (Immediate Action Required)
1. **Exact name duplicates**: [Count] instances
   - Impact: Agent cannot reliably select correct tool
   - Action: Rename all duplicates with server/context prefix

2. **Identical descriptions for different tools**: [Count] instances
   - Impact: Descriptions provide no differentiation
   - Action: Rewrite all descriptions to be unique and specific

### High Priority Issues (Address Soon)
1. **Similar names with overlapping descriptions**: [Count] instances
2. **Vague descriptions (<20 chars)**: [Count] instances
3. **Typos or grammatical errors**: [Count] instances

### Medium Priority Issues (Improve Over Time)
1. **Inconsistent naming conventions**: [Count] instances
2. **Missing context in descriptions**: [Count] instances
3. **Unexplained acronyms**: [Count] instances

### Low Priority Issues (Nice to Have)
1. **Style inconsistencies**: [Count] instances
2. **Could be more descriptive**: [Count] instances

---

## 6. Failure Mode Analysis

### Scenario 1: Ambiguous Tool Selection
**Context**: User asks "Get the billing details for customer 42"

**Problem**: Multiple tools match:
- `get_user` (mcp-inventory) - "Get user"
- `get_user` (mcp-billing) - "Get the billing profile for a customer..."

**Agent Behavior**: 
- May randomly select one
- May ask for clarification (inefficient)
- May try all three (wasteful)

**Impact**: Wrong data returned, wasted API calls, poor user experience

**Solution**: Rename and improve descriptions:
- `get_inventory_user` - "Retrieve a warehouse operator by user ID, including assigned warehouses and role."
- `get_billing_customer` - "Get the billing profile for a customer, including payment method and billing address."

### Scenario 2: Missing Tool Due to Vague Description
**Context**: User asks "Apply a refund for invoice INV-2024-001"

**Problem**: Tool exists but description is too vague:
- `do_action` - "Perform action" (no hint of what actions are supported)

**Agent Behavior**: May not recognize this tool handles refunds

**Impact**: Agent says "no tool available" when one exists

**Solution**: Rename and improve description:
- `issue_refund` - "Issue a full or partial refund for a paid invoice by invoice ID."

---

## 7. Recommendations

### Immediate Actions (Critical)

| Issue | Affected Tools | Recommendation | Priority |
|-------|----------------|----------------|----------|
| Duplicate `get_user` | mcp-inventory, mcp-billing | Rename to `get_inventory_user`, `get_billing_customer` | Critical |
| Vague description | `get_user` (mcp-inventory) | Rewrite to explain which user and what data | Critical |
| Vague description | `do_action` (mcp-billing) | Rename and rewrite to describe the actual action | Critical |

### Short-term Improvements (High Priority)

1. **Rewrite all descriptions under 20 characters** to be more specific
2. **Add context** to generic verbs (Get what? From where? For what purpose?)
3. **Clarify overlapping tools** — state when to use each, or merge them
4. **Standardize naming conventions** across all servers

### Long-term Enhancements (Medium Priority)

1. **Establish naming guidelines** for new tools
2. **Create description templates** by tool category
3. **Implement automated validation** for new tool definitions
4. **Regular audits** (quarterly) to maintain quality

---

## 8. Prevention Guidelines

### Naming Conventions

**Standard Format**: `<verb>_<object>_<context>`

Examples:
- ✅ `get_user_profile`
- ✅ `list_active_tasks`
- ✅ `create_security_policy`
- ❌ `get_data` (too vague)
- ❌ `getUserInfo` (wrong case)

**Verb Guidelines**:
- `get_` - Retrieve single item
- `list_` - Retrieve multiple items
- `create_` - Create new resource
- `update_` - Modify existing resource
- `delete_` - Remove resource
- `search_` - Query with filters

### Description Quality Standards

**Minimum Requirements**:
1. Length: At least 40 characters
2. Structure: "[Verb] [specific object] [context/purpose]"
3. Clarity: No unexplained acronyms
4. Uniqueness: Distinguishable from similar tools
5. Accuracy: Matches actual functionality

**Good Examples**:
- ✅ "Retrieve user authentication profile including permissions and role assignments"
- ✅ "List all active security policies with their associated rules and enforcement status"
- ✅ "Create a new data classification tag with specified category and sensitivity level"

**Bad Examples**:
- ❌ "Get user" (too short, no context)
- ❌ "Get DM extraction profile" (unexplained acronym)
- ❌ "Get data" (too vague)

### Review Checklist for New Tools

Before adding a new tool, verify:

- [ ] Name is unique across all servers
- [ ] Name follows naming convention
- [ ] Description is at least 40 characters
- [ ] Description explains what, why, and context
- [ ] No unexplained acronyms
- [ ] No typos or grammatical errors
- [ ] Distinguishable from similar tools
- [ ] Tested with sample agent queries

---

## 9. Validation Rules (Automated Checks)

### Proposed Linting Rules

```yaml
rules:
  naming:
    - no_duplicate_names_per_server: error
    - snake_case_required: error
    - min_name_length: 5
    - max_name_length: 50
    - no_special_chars: error
    
  descriptions:
    - min_length: 40
    - max_length: 200
    - must_start_with_capital: warning
    - must_end_with_period: warning
    - no_typos_in_common_words: error
    - no_unexplained_acronyms: warning
    - must_differ_from_name: error
    
  uniqueness:
    - no_identical_descriptions: error
    - similarity_threshold: 0.8  # Flag if >80% similar
    
  quality:
    - must_contain_verb: warning
    - must_contain_object: warning
    - must_contain_context: info
```

### Implementation Suggestions

1. **Pre-commit hook**: Run validation before committing tool definitions
2. **CI/CD integration**: Fail builds if critical rules violated
3. **Dashboard**: Track tool quality metrics over time
4. **Alerts**: Notify when new tools violate guidelines

---

## 10. Next Steps

### Immediate (This Week)
1. [ ] Fix critical naming collisions (rename duplicate tools)
2. [ ] Correct typos in descriptions
3. [ ] Rewrite descriptions under 20 characters

### Short-term (This Month)
1. [ ] Expand all acronyms in descriptions
2. [ ] Standardize naming conventions across servers
3. [ ] Implement validation rules in CI/CD

### Long-term (This Quarter)
1. [ ] Establish tool definition guidelines
2. [ ] Create automated linting tool
3. [ ] Schedule quarterly audits
4. [ ] Train teams on best practices

---

## Appendix A: Complete Tool List

[Include full inventory with quality scores]

## Appendix B: Similarity Matrix

[Include matrix showing similarity scores between all tools]

## Appendix C: Server-by-Server Analysis

[Detailed breakdown for each server]