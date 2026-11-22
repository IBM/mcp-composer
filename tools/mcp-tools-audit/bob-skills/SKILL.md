---
name: tool-audit
description: Audit MCP tool definitions to identify naming collisions, description overlaps, and ambiguities that may confuse agent decision-making
---

# Tool Definition Audit Skill

This skill performs a systematic audit of MCP tool definitions to identify potential sources of confusion for agent decision-making.

## Parameters Required

The user will provide the JSON file path in their request. If not provided, ask for:
- **tools_json_path**: Path to the JSON file containing tool definitions (e.g., `tools.json`)

## Expected JSON Format

The skill expects a JSON structure with:
```json
{
  "active": {
    "server-name": [
      {"name": "tool_name", "description": "Tool description"}
    ]
  },
  "deactivated": ["server-list"]
}
```

**Note**: Some servers may have ERROR entries (authentication/connectivity failures) that should be excluded from real tool counts.

## Audit Process

<Steps>
<Step>
**Load and Parse Tool Definitions**
- Use read_file tool to load the JSON file
- Parse the JSON structure (handle both "active" and "deactivated" sections)
- **CRITICAL**: Count actual tools and servers properly using execute_command with Python:
  ```python
  import json
  with open('file.json', 'r') as f:
      data = json.load(f)
  
  # Count active servers and tools
  active_servers = len(data['active'])
  total = 0
  for server, tools in data['active'].items():
      count = len(tools)
      total += count
      print(f'{server}: {count} tools')
  print(f'TOTAL: {total} tools')
  print(f'Active servers: {active_servers}')
  
  # Count deactivated servers
  deactivated = data.get('deactivated', [])
  deactivated_count = len(deactivated)
  print(f'Deactivated servers: {deactivated_count}')
  if deactivated_count > 0:
      print(f'Deactivated list: {deactivated}')
  ```
  - **NEVER estimate** based on file size, line count, or manual counting
  - **ALWAYS use Python** to count tools and servers programmatically
  - Count both active AND deactivated servers
  - Iterate through each server in "active" section
  - Count tools per server: `len(tools_array)`
  - Count deactivated servers: `len(data.get('deactivated', []))`
  - Identify ERROR tools (name starts with "ERROR" or description contains "HTTP Error")
  - Calculate: Real tools = Total entries - ERROR tools
  - Verify total by summing all server counts
- Extract all tool names and descriptions from active servers
- Create inventory with server/product associations
- Calculate statistics:
  - Total active servers: `len(data['active'])`
  - Total deactivated servers: `len(data.get('deactivated', []))`
  - List deactivated server names if any exist
  - Total real tools (excluding ERROR placeholders)
  - Tools per server breakdown with accurate percentages
  - Description length distribution
  - Quality score distribution
- **VALIDATION**: Before proceeding, verify that:
  - Sum of all server tool counts equals reported total
  - Percentages add up to 100%
  - No server has 0 tools unless it's truly empty or has ERROR
  - Deactivated server count matches the actual list length
</Step>

<Step>
**Identify Naming Collisions**

Use Python to systematically find all duplicates:

```python
import json
from collections import defaultdict

with open('file.json', 'r') as f:
    data = json.load(f)

# Track all tool names and their locations
tool_locations = defaultdict(list)

for server, tools in data['active'].items():
    for tool in tools:
        tool_name = tool['name']
        tool_locations[tool_name].append({
            'server': server,
            'description': tool['description']
        })

# Find duplicates
within_server_dupes = []
cross_server_dupes = []

for tool_name, locations in tool_locations.items():
    if len(locations) > 1:
        # Check if same server
        servers = [loc['server'] for loc in locations]
        if len(set(servers)) < len(servers):
            # Within-server duplicate
            within_server_dupes.append((tool_name, locations))
        else:
            # Cross-server duplicate
            cross_server_dupes.append((tool_name, locations))
```

**Categorize duplicates by severity:**

1. **CRITICAL - Within-Server Duplicates:**
   - Same tool name appears multiple times in the SAME server
   - Agent cannot distinguish which to use
   - Check if descriptions are identical or different
   - If identical: likely error, remove duplicate
   - If different: rename to distinguish functions

2. **HIGH PRIORITY - Cross-Server Duplicates with Different Descriptions:**
   - Same tool name in different servers with different descriptions
   - May confuse agent about which server to use
   - Requires investigation and possible renaming

3. **ACCEPTABLE - Cross-Server Duplicates with Identical Descriptions:**
   - Same tool name in different servers with identical descriptions
   - Indicates intentionally mirrored/redundant services
   - Provides load balancing and failover
   - No action required unless descriptions diverge

**Additional checks:**
- Identify truncated names (ending with incomplete words or "xxx" placeholders)
- Find names with missing underscores (e.g., "findassetname")
- Detect similar tool names (1-2 character differences)
- Identify naming pattern inconsistencies
- Document which servers have colliding names with line numbers

**Report format:**
- List within-server duplicates first (most critical)
- List cross-server duplicates with different descriptions
- Note cross-server duplicates with identical descriptions as acceptable
- Provide counts: X unique tool names, Y total tools, Z duplicates
</Step>

<Step>
**Analyze Description Overlaps**
- Identify tools with identical descriptions (especially if names differ)
- Group tools by description to find duplicates
- Detect vague or generic descriptions (e.g., "Get data", "Get info", "Get user")
- Flag descriptions under 15 characters as critically vague
- Flag descriptions under 20 characters as high priority
- Identify unexplained acronyms (e.g., SKU, ETA, or PO without spelling them out)
- Find typos in descriptions using common word checking
</Step>

<Step>
**Detect Ambiguous Descriptions**
- Find descriptions that are too short (<20 characters)
- Identify descriptions lacking context (what, why, for whom)
- Flag descriptions with typos or grammatical errors
- Detect descriptions that don't explain the tool's purpose
- Find descriptions that are just the tool name rephrased
- Identify missing information (which resource, what data, what format)
</Step>

<Step>
**Categorize Issues by Severity**
- **Critical**:
  - Exact name duplicates within same server
  - Exact name duplicates with different descriptions
  - Typos in descriptions
  - ERROR tools (authentication/connectivity failures)
  - Descriptions under 10 characters
- **High**:
  - Descriptions under 20 characters
  - Truncated names with "xxx" or incomplete words
  - Names missing underscores
  - Unexplained acronyms
- **Medium**:
  - Inconsistent naming patterns
  - Missing context in descriptions
  - Could be more specific
- **Low**:
  - Style inconsistencies
  - Minor improvements
</Step>

<Step>
**Generate Failure Scenarios**
Create 3-5 concrete failure scenarios showing:
- User query example
- Available tools that match
- Why agent cannot distinguish
- What goes wrong (wrong selection, no selection, multiple calls)
- Impact on user experience
Focus on the most critical issues (duplicates, vague descriptions, typos)
</Step>

<Step>
**Create Actionable Recommendations**
For each critical and high priority issue, provide:
- Specific suggested renaming with full new name
- Complete rewritten descriptions (40-200 characters)
- Before/after examples in clear format
- Rationale explaining why the change improves clarity
- Estimated effort (time) to implement
Group recommendations by:
- Immediate actions (this week)
- Short-term improvements (this month)
- Long-term enhancements (this quarter)
</Step>

<Step>
**Develop Prevention Guidelines**
Create guidelines for future tool definitions:
- Naming conventions and patterns
- Description quality standards
- Differentiation requirements
- Review checklist for new tools
</Step>

<Step>
**Format Deliverable**
Create a concise, actionable report (400-500 lines) including:
- **Executive summary** with:
  - ACCURATE server counts: X active servers, Y deactivated servers
  - List deactivated server names if any exist
  - ACCURATE tool count (real tools, not file lines or estimates)
  - Breakdown: X real tools (Y total entries, Z ERROR placeholders)
  - Overall health score and top 5 urgent actions
- **Statistics table**:
  - Tools by server (with actual counts)
  - Deactivated servers listed by name
  - Issue counts by severity
  - Percentage calculations based on real tool count
- Critical issues section with specific examples
- High priority issues with concrete recommendations
- 3-5 failure scenarios demonstrating real impact
- Actionable recommendations with time estimates
- Prevention guidelines (naming conventions, description standards)
- Validation rules for automation
- Next steps with timeline (week 1, month 1, quarter 1)
- Top 50 issues appendix for quick reference

Keep the report focused and scannable with:
- Clear severity indicators (🔴 🟡 🟠)
- Tables for easy comparison
- Code blocks for before/after examples
- Checkboxes for action items
- **Accurate counts throughout** (verify against actual data)
</Step>
</Steps>

## Analysis Techniques

Use practical pattern matching and analysis:
- **Exact duplicates**: Group by name, check if appears >1 time
- **Truncated names**: Look for patterns like "xxx", incomplete words, missing underscores
- **Vague descriptions**: Check length (<10 critical, <20 high priority)
- **Typos**: Common words like "health" vs "gealth", "earliest" vs "rarliest"
- **Acronyms**: Uppercase sequences without expansion (e.g., SKU, ETA, PO)
- **Missing context**: Descriptions that are just "Get [noun]" without details

For advanced analysis, refer to `analysis-techniques.md` for:
- Levenshtein distance for name similarity
- Cosine similarity for description overlap
- Statistical quality metrics

## Output Format

Create a focused, actionable report (not the full template):
- **Executive Summary**: Health score, top 5 urgent actions
- **Critical Issues**: With line numbers and specific fixes
- **High Priority Issues**: Grouped by type (vague, truncated, acronyms)
- **Failure Scenarios**: 3-5 concrete examples
- **Recommendations**: Immediate, short-term, long-term with time estimates
- **Prevention Guidelines**: Naming conventions, description standards
- **Statistics**: Tools by server, quality distribution
- **Next Steps**: Weekly/monthly/quarterly action plan
- **Appendix**: Top 50 issues for quick reference

Use tables, checkboxes, and severity indicators (🔴🟡🟠) for scannability.
For full template reference, see `report-template.md`

## Quality Standards

Ensure the audit meets these criteria:
- ✅ All tools analyzed (count matches JSON)
- ✅ Issues categorized by severity (Critical/High/Medium/Low)
- ✅ Each critical issue has specific fix with line number
- ✅ Recommendations include before/after examples
- ✅ Time estimates provided for implementation
- ✅ Failure scenarios demonstrate real impact
- ✅ Prevention guidelines are actionable
- ✅ Report is concise and scannable (400-500 lines)

For complete checklist, refer to `quality-checklist.md`

## Key Patterns to Look For

Based on real-world audits, prioritize finding:
1. **Exact duplicates within same server** (most critical)
2. **Truncated names** (xxx, incomplete words, missing _)
3. **Descriptions under 15 characters** (critically vague)
4. **Typos in common words** (health, earliest, dashboard)
5. **ERROR tools** (authentication/connectivity issues)
6. **Unexplained acronyms** (e.g., SKU, ETA, or PO without expansion)
7. **Generic descriptions** ("Get user", "Get data", "Get info")
8. **Missing context** (which resource? what data? for whom?)