# Tool Audit Skill

A comprehensive skill for auditing MCP tool definitions to identify naming collisions, description overlaps, and ambiguities that may confuse agent decision-making.

## Overview

This skill performs systematic analysis of tool catalogs to improve tool selection reliability by identifying and resolving:
- Naming collisions (duplicate or similar names)
- Description overlaps (identical or highly similar descriptions)
- Ambiguous or low-quality descriptions
- Inconsistent naming conventions
- Unexplained acronyms and typos

## Quick Start

### Prerequisites
- Bob must be in **Advanced mode** (skills only work in Advanced mode)
- A JSON file containing tool definitions (see format below)

### Usage

1. **Activate the skill** by asking Bob to audit your tools:
   ```
   "Audit the tool definitions in tools.json"
   ```

2. **Provide the file path** when prompted:
   ```
   ./tools.json
   ```

3. **Review the generated report** which includes:
   - Complete tool inventory
   - Identified issues by severity
   - Concrete recommendations
   - Prevention guidelines

## Expected Input Format

The skill expects a JSON file with the following structure:

```json
{
  "active": {
    "server-name-1": [
      {
        "name": "tool_name",
        "description": "Tool description"
      }
    ],
    "server-name-2": [
      {
        "name": "another_tool",
        "description": "Another description"
      }
    ]
  }
}
```

## What the Skill Does

### 1. Data Collection
- Loads and parses the JSON file
- **Counts tools programmatically** (never estimates from file size)
- **Identifies ERROR tools** (auth/connectivity placeholders)
- Calculates: Real tools = Total entries - ERROR placeholders
- Extracts all tool names and descriptions
- Creates inventory with server associations
- Validates data structure

### 2. Naming Analysis
- Identifies exact duplicate names
- Finds similar names using fuzzy matching
- Detects naming pattern inconsistencies
- Flags naming convention violations

### 3. Description Analysis
- Finds identical descriptions
- Calculates similarity scores
- Identifies vague or too-short descriptions
- Detects typos and grammatical errors
- Flags unexplained acronyms

### 4. Issue Categorization
- **Critical**: Exact duplicates, severe ambiguity
- **High**: Similar names with overlaps, typos
- **Medium**: Vague descriptions, inconsistencies
- **Low**: Style improvements

### 5. Recommendations
- Specific renaming suggestions
- Rewritten descriptions with examples
- Prevention guidelines
- Validation rules for automation

### 6. Report Generation
- Structured markdown report
- Tables for easy scanning
- Concrete before/after examples
- Prioritized action plan

## Output

The skill generates a comprehensive report including:

1. **Executive Summary**
   - **Accurate tool count** (real tools, not file lines or estimates)
   - Breakdown: X real tools (Y total entries, Z ERROR placeholders)
   - Key findings and statistics
   - Overall health score
   - Top recommendations

2. **Tool Inventory**
   - Complete list of tools
   - Tools per server
   - Issue counts

3. **Detailed Analysis**
   - Naming collisions with examples
   - Description overlaps with similarity scores
   - Ambiguous descriptions with quality scores
   - Categorized by severity

4. **Failure Scenarios**
   - Real-world examples of agent confusion
   - Impact assessment
   - Proposed solutions

5. **Recommendations**
   - Immediate actions (critical fixes)
   - Short-term improvements
   - Long-term enhancements
   - Before/after examples

6. **Prevention Guidelines**
   - Naming conventions
   - Description quality standards
   - Review checklist
   - Validation rules

## Supporting Files

- **[`SKILL.md`](SKILL.md)**: Main skill instructions
- **[`analysis-techniques.md`](analysis-techniques.md)**: Detailed analysis methods and algorithms
- **[`report-template.md`](report-template.md)**: Comprehensive report structure and format
- **[`quality-checklist.md`](quality-checklist.md)**: Quality assurance checklist
- **[`example-analysis.md`](example-analysis.md)**: Concrete example using real data

## Example Issues Detected

### Critical: Cross-Server Duplicates
```
Tool: get_user (appears in both mcp-inventory and mcp-billing)
Descriptions differ: "Get user" vs "Get the billing profile for a customer..."
Problem: Agent cannot determine which server to call
Recommendation: Rename to get_inventory_user and get_billing_customer
```

### Critical: Vague Descriptions
```
Tool: get_user (mcp-inventory)
Description: "Get user" (8 characters)
Problem: No context — which user? what data?
Recommendation: "Retrieve a warehouse operator by user ID, including
                 assigned warehouses and role."

Tool: do_action (mcp-billing)
Description: "Perform action" (14 characters)
Problem: Generic — gives no hint about what action is performed
Recommendation: "Issue a full or partial refund for a paid invoice
                 by invoice ID."
```

### High Priority: Overlapping Descriptions
```
Tool 1: list_items (mcp-inventory)
Description: "List inventory items, optionally filtered by warehouse or category."
Tool 2: search_items (mcp-inventory)
Description: "List inventory items, optionally filtered by warehouse, category, or keyword."
Problem: search_items is a superset; agent cannot choose between them
Recommendation: Remove list_items or distinguish their use cases clearly
```

## Best Practices

### For Tool Creators
1. **Use descriptive names**: `get_user_profile` not `get_user`
2. **Write detailed descriptions**: Minimum 40 characters
3. **Explain context**: What, why, and for whom
4. **Expand acronyms**: First use should spell out
5. **Follow conventions**: Consistent verb-noun-context pattern

### For Auditors
1. **Count accurately**: Always use programmatic counting, never estimate
2. **Identify ERROR tools**: Exclude authentication/connectivity placeholders from counts
3. **Be thorough**: Analyze all tools, not just problematic ones
4. **Provide examples**: Show concrete before/after
5. **Prioritize issues**: Focus on critical problems first
6. **Think like an agent**: Consider how tools will be selected
7. **Be actionable**: Give specific, implementable recommendations
8. **Verify percentages**: Ensure all percentages are based on real tool count

## Validation Rules

The skill can help define automated validation rules:

```yaml
naming:
  - no_duplicate_names_per_server: error
  - snake_case_required: error
  - min_name_length: 5

descriptions:
  - min_length: 40
  - no_typos_in_common_words: error
  - must_differ_from_name: error
  
uniqueness:
  - no_identical_descriptions: error
  - similarity_threshold: 0.8
```

## Integration

The skill itself runs inside Bob — there is no separate CLI binary. To integrate quality checks
into automated workflows, use the Python counting snippet from `example-analysis.md` or write a
custom script that validates the JSON structure before committing tool definition changes.

## Customization

You can customize the skill by modifying:

1. **Similarity thresholds** in `analysis-techniques.md`
2. **Quality standards** in `quality-checklist.md`
3. **Report format** in `report-template.md`
4. **Severity levels** in `SKILL.md`

## Troubleshooting

### Issue: JSON parsing error
**Solution**: Validate JSON format using `jq` or online validator

### Issue: Too many tools to analyze
**Solution**: Process in batches by server or use sampling

### Issue: Unclear recommendations
**Solution**: Review `example-analysis.md` for concrete examples

### Issue: Missing context
**Solution**: Consult with tool creators for functionality details

## Contributing

To improve this skill:

1. Add more analysis techniques to `analysis-techniques.md`
2. Enhance report template with new sections
3. Add more examples to `example-analysis.md`
4. Update quality checklist based on experience
5. Share lessons learned

## Resources

- [MCP Jam](https://www.mcpjam.com/) - MCP tool catalog
- [Bob Skills Documentation](https://docs.bob.ai/skills) - General skill creation
- [MCP specification](https://spec.modelcontextprotocol.io/) - Reference for tool definition format

## License

This skill is part of the MCP Composer project.

## Support

For questions or issues:
1. Check `example-analysis.md` for concrete examples
2. Review `quality-checklist.md` for common pitfalls
3. Consult `analysis-techniques.md` for methodology
4. Open an issue on this repository

---

**Version**: 1.0.0  
**Last Updated**: 2026-05-12  
**Maintainer**: community contributor (open an issue on this repository)