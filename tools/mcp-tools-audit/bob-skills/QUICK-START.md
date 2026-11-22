# Quick Start Guide: Tool Audit Skill

## What This Skill Does

Analyzes MCP tool definitions to find:
- ❌ Duplicate tool names
- ❌ Vague or confusing descriptions  
- ❌ Naming inconsistencies
- ❌ Typos and errors
- ✅ Provides actionable recommendations

## How to Use

### Step 1: Prepare Your Data
Ensure you have a JSON file with tool definitions:
```json
{
  "active": {
    "server-name": [
      {"name": "tool_name", "description": "Tool description"}
    ]
  }
}
```

### Step 2: Activate the Skill
In Bob (Advanced mode), say:
```
"Audit the tool definitions in my tools file"
```
or
```
"Run tool-audit on tools.json"
```

### Step 3: Provide File Path
When Bob asks, provide the path:
```
./tools.json
```

### Step 4: Review Results
Bob will generate a comprehensive report with:
- 📊 Statistics and metrics
- 🔴 Critical issues requiring immediate action
- 🟡 High/medium priority improvements
- ✅ Specific recommendations with examples
- 📋 Prevention guidelines for future tools

## Example Output

```markdown
## Critical Issues Found

1. **Duplicate Tool Name**: `get_user`
   - Appears in both mcp-inventory and mcp-billing with different functionality
   - **Fix**: Rename to `get_inventory_user` and `get_billing_customer`

2. **Vague Description**: `do_action` (mcp-billing)
   - Current: "Perform action" (14 chars)
   - **Fix**: "Issue a full or partial refund for a paid invoice by invoice ID."

3. **Vague Description**: `get_user` (mcp-inventory)
   - Current: "Get user" (8 chars)
   - **Fix**: "Retrieve a warehouse operator by user ID, including assigned warehouses and role."
```

## What You Get

1. **Executive Summary** - Key findings at a glance
2. **Complete Inventory** - All tools analyzed
3. **Issue Categories** - Organized by severity
4. **Concrete Examples** - Before/after comparisons
5. **Action Plan** - Prioritized next steps
6. **Prevention Guidelines** - Standards for future tools

## Common Issues Detected

| Issue Type | Example | Severity |
|------------|---------|----------|
| Cross-server duplicates | `get_user` in both mcp-inventory and mcp-billing | 🔴 Critical |
| Vague descriptions | "Get user", "Perform action" | 🔴 Critical |
| Overlapping descriptions | `list_items` / `search_items` nearly identical | 🟡 High |
| Similar names | `get_user` vs `get_users` (1 char) | 🟡 High |

## Tips for Best Results

✅ **Do:**
- Use the skill in Advanced mode
- Provide complete JSON file path
- Review all recommendations carefully
- Implement critical fixes first
- Share results with your team

❌ **Don't:**
- Skip the file path parameter
- Ignore critical issues
- Make changes without testing
- Forget to update documentation

## Need Help?

- 📖 See [`README.md`](README.md) for full documentation
- 📝 Check [`example-analysis.md`](example-analysis.md) for concrete examples
- ✅ Use [`quality-checklist.md`](quality-checklist.md) to verify completeness
- 🔧 Review [`analysis-techniques.md`](analysis-techniques.md) for methodology

## Next Steps After Audit

1. **Immediate** (This Week)
   - Fix critical naming collisions
   - Correct typos in descriptions
   - Resolve exact duplicates

2. **Short-term** (This Month)
   - Rewrite vague descriptions
   - Standardize naming conventions
   - Expand all acronyms

3. **Long-term** (This Quarter)
   - Implement validation rules
   - Create tool definition guidelines
   - Schedule regular audits

## Success Metrics

Your audit is successful when:
- ✅ All critical issues identified
- ✅ Specific recommendations provided
- ✅ Examples show before/after
- ✅ Prevention guidelines created
- ✅ Team can act on findings immediately

---

**Ready to start?** Just ask Bob: *"Audit my tool definitions"*