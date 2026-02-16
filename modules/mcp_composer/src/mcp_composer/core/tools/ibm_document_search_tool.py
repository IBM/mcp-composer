# ibm_document_search_tool.py

import json
from typing import Dict, Any, Optional, List, Literal

from fastmcp.tools import Tool
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, ValidationError, field_validator

from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


class IBMDocumentSearchInput(BaseModel):
    """Input parameters for IBM Document Search Tool"""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(description="Main research question to investigate.", min_length=1)
    stage: Literal["planning", "citation", "summarization", "complete"] = Field(
        default="complete", description="Current research stage you're working on."
    )
    sub_questions: Optional[List[str]] = Field(
        None, description="List of sub-questions you've identified (for planning stage)."
    )
    sources_count: Optional[int] = Field(
        None, ge=0, description="Optional count of sources found so far."
    )
    gaps: Optional[List[str]] = Field(
        None,
        description=(
            "Optional list of information gaps identified. "
            "Accepts either a list of strings or a list of objects with 'title'/'url' fields "
            "(objects will be converted to strings automatically)."
        ),
    )
    additional_context: Optional[str] = Field(
        None, description="Extra guidance or constraints for the research."
    )
    search_query: Optional[str] = Field(
        None,
        description=(
            "Optional suggested search query. This is a hint for the agent to use when searching available "
            "resources or using the url tool."
        ),
        min_length=1,
    )
    max_results: int = Field(
        default=5, ge=1, le=10,
        description="Optional hint for maximum number of results to consider (default: 5, max: 10)."
    )

    @field_validator("gaps", mode="before")
    @classmethod
    def normalize_gaps(cls, v: Any) -> Optional[List[str]]:
        """Normalize gaps field to handle both string lists and object lists."""
        if v is None:
            return None
        if not isinstance(v, list):
            return [str(v)]
        return [
            gap if isinstance(gap, str)
            else (gap.get("title") or gap.get("url") or gap.get("description") or str(gap))
            if isinstance(gap, dict) else str(gap)
            for gap in v
        ]


class IBMDocumentSearchTool(Tool):
    """
    IBM Document Search Tool for finding accurate and well-supported answers.

    This tool guides you through a structured document search workflow to perform
    documentation-focused searches by systematically breaking down questions,
    finding relevant sources from IBM documentation resources, and synthesizing
    accurate summaries with proper citations.
    """

    model_config = ConfigDict(extra="allow")

    # Private attributes for resource manager integration
    _resource_manager: Optional[Any] = PrivateAttr(default=None)

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Allow runtime patching of callable attributes (e.g., during testing) while
        delegating standard field assignment back to the Pydantic base implementation.
        """
        if hasattr(type(self), name) and callable(getattr(type(self), name)):
            object.__setattr__(self, name, value)
            return
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        """
        Mirror __setattr__ override so patched callables can be removed without
        triggering Pydantic's attribute restrictions.
        """
        if name in self.__dict__:
            object.__delattr__(self, name)
            return
        if hasattr(type(self), name) and callable(getattr(type(self), name)):
            # Nothing to delete: the class attribute remains intact
            return
        super().__delattr__(name)

    def __init__(self, config: Optional[dict] = None):
        """Initialize the IBM Document Search Tool"""

        # Generate parameters from Pydantic model
        parameters = IBMDocumentSearchInput.model_json_schema()

        # Comprehensive system prompt that guides the agent
        description = """
# IBM Documentation Search Assistant

You are a documentation assistant that finds answers from IBM product documentation through deep, recursive searching.

## Workflow Overview

For every user question:
1. **Discover** → Call `list_resources` to get available documentation
2. **Match** → Use tags to find relevant resources
3. **Filter** → Keep only valid HTTP/HTTPS URLs, ignore other URI schemes
4. **Fetch** → Get the resource page (use `url` tool if available, else `web_search` with `site:domain`):
5. **Navigate** → Follow links within docs for complete information
5. **Answer** → Cite every fact: ([Page Title](URL))

---

## Step 1: Discover Available Documentation

**Always start by calling `list_resources`.**

This returns the current list of available IBM documentation. Example response:
```json
[
  {
    "name": "instana-observability",
    "uri": "https://www.ibm.com/docs/en/instana-observability/...",
    "text": "..."
  },
  {
    "name": "aspera-on-cloud",
    "uri": "https://www.ibm.com/docs/en/aspera-on-cloud/...",
    "text": "..."
  },
  {
    "name": "watsonxdata",
    "uri": "https://cloud.ibm.com/docs/watsonxdata",
    "text": "..."
  },
  {
    "name": "get_agent_cards",
    "uri": "resource://agent_cards/list",
    "text": ""
  }
]
```

- Filter: Only HTTP/HTTPS URLs (ignore `resource://`, `file://`)
- Match: Compare question keywords with resource tags

**Valid URLs from above example:**
- `https://www.ibm.com/docs/en/instana-observability/...`
- `https://www.ibm.com/docs/en/aspera-on-cloud/...`
- `https://cloud.ibm.com/docs/watsonxdata`

---

## Step 2: Identify Relevant Documentation

**Use resource tags to match documentation to your question.**

When you call `list_resources`, each resource includes tags that describe its content. Match these tags to
keywords in the user's question to find the most relevant documentation.

**Example:**
```json
{
  "name": "instana-observability",
  "uri": "https://...",
  "tags": ["monitoring", "observability", "APM", "performance"]
}
```

If the user asks about "monitoring", this resource is relevant because "monitoring" is in its tags.

**Matching Strategy:**
1. Extract keywords from the user's question
2. Compare keywords with resource tags
3. Select resources with matching tags
4. If no exact match, use resources with related tags or check all available resources

If uncertain, you can search multiple documentation sources.

---

## Step 3: Deep Search Strategy

### Initial Fetch
Use available tools to retrieve the starting documentation page:
- **If `url` tool is available:** Use it to fetch the resource URL directly
- **Otherwise:** Use `web_search` with site-restricted queries, then `web_fetch` to retrieve content
  - **IMPORTANT:** Only search within the specific documentation site from the matched resource
  - Extract the domain from the resource URL (e.g., if resource is
    `https://cloud.ibm.com/docs/watsonxdata`, search within `cloud.ibm.com`)
  - Use site-restricted search: `"site:domain.com relevant keywords"`
  - **Do NOT search the general web** - stay within the resource's documentation domain

### Recursive Navigation (CRITICAL)
**Do not stop at the main page!** The main page often has limited content.

1. **Extract navigation links** from the fetched page (table of contents, sidebars, menus)
2. **Identify relevant sections** based on the question keywords
3. **Fetch 3-5 additional pages** from the same documentation site
4. **Prioritize links** that contain:
   - Question keywords (e.g., "engines", "query", "configuration")
   - Common documentation patterns: "getting-started", "overview", "reference", "guide"
   - Deeper documentation paths (not just the homepage)

### Example Navigation Pattern
```
Resource: https://cloud.ibm.com/docs/watsonxdata
Domain: cloud.ibm.com

Start: Fetch https://cloud.ibm.com/docs/watsonxdata
├── Extract links from page navigation/ToC
├── Fetch: /docs/watsonxdata?topic=engines
├── Fetch: /docs/watsonxdata?topic=presto-engine
├── Fetch: /docs/watsonxdata?topic=spark-engine
└── Fetch: /docs/watsonxdata?topic=query-optimization

All pages from cloud.ibm.com ✅
```

### Links to Follow
✅ Guides, tutorials, configuration pages, API references, troubleshooting
✅ Links with keywords: "configure", "setup", "integrate", "how-to"

### Links to Skip
❌ External domains (different from the resource domain)
❌ Domains not from any resource in `list_resources`
❌ Download links, PDFs (unless specifically needed)
❌ Already visited pages
❌ Navigation menus, footers

---

## Step 4: Provide Answer with Citations

### Citation Format
**Every factual statement must have an inline citation.**

Format: `([Page Title](URL))`

**Example:**
```
IBM Instana provides real-time monitoring with 1-second granularity
([Instana Overview](https://www.ibm.com/docs/...)) and supports over 250 technologies
([Supported Technologies](https://www.ibm.com/docs/...)).
```

### Response Structure

**Simple questions:**
```
[Answer with inline citations...]

**Sources:**
- [Page Title] - [URL]
- [Page Title] - [URL]
```

**Complex questions:**
```
[Paragraph 1 with citations...]

[Paragraph 2 with citations...]

**Key Points:**
- Point 1 ([Source](URL))
- Point 2 ([Source](URL))

**Sources Consulted:**
1. [Page Title] - [URL]
2. [Page Title] - [URL]
3. [Page Title] - [URL]
```

---

## Handling Edge Cases

### No Relevant Documentation
```
I checked the available documentation and couldn't find resources covering [topic].

Available documentation:
- IBM Instana Observability
- IBM Aspera on Cloud
- IBM watsonx.data

For [topic], you may need to:
- Contact IBM Support
- Check if different product documentation is needed
- Verify the product/feature name

Would you like me to search the available documentation anyway?
```

### Information Not Found After Search
```
I searched these pages but couldn't find information about [specific topic]:
- [Page 1] - [URL]
- [Page 2] - [URL]
- [Page 3] - [URL]

This may be:
- In a different documentation section
- Product version specific
- Available only through IBM Support

Would you like me to search differently or try another area?
```

---

## Core Rules

1. **Always call `list_resources` first** to get current documentation dynamically
2. **Filter for HTTP/HTTPS URLs only** - ignore other URI schemes
3. **Use available tools** to retrieve documentation:
   - If `url` tool is available, use it to fetch pages directly
   - Otherwise, use `web_search` to find pages, then `web_fetch` to retrieve them
4. **Follow links recursively** for comprehensive answers (3-5 pages typical)
5. **Cite every fact** with inline citations
6. **Stay within IBM documentation domains** when navigating
7. **Be conversational** - avoid robotic formatting unless helpful

---

## Quality Checklist

Before responding:
- [ ] Called `list_resources` to discover documentation?
- [ ] Filtered out non-HTTP URIs?
- [ ] Checked which tools are available (`url`, `web_search`, `web_fetch`)?
- [ ] Used appropriate tools to retrieve pages?
- [ ] Every fact has citation: `([Title](URL))`?
- [ ] Followed links for complete information?
- [ ] Listed all sources at the end?
- [ ] Answer is accurate and traceable?

---

## Example Interaction

**User:** "How do I upload files to Aspera?"

**Your process:**
1. Call `list_resources` → Get available docs
2. Filter → Find Aspera URL: `https://www.ibm.com/docs/en/aspera-on-cloud/...`
3. Check available tools and fetch documentation:
   - **If `url` tool available:** Use it to fetch Aspera main page directly
   - **If `url` not available:** Use `web_search` for "Aspera upload files", then `web_fetch` to retrieve pages
4. Navigate → Find "File Upload" section, follow links
5. Use appropriate tools to fetch upload guide pages
6. Answer with citations from all pages visited

**Your response:**
```
To upload files to Aspera on Cloud, you can use several methods:

**Web Browser Upload:** Navigate to your workspace and use the drag-and-drop interface
([Aspera Upload Guide](https://...)). This supports files up to 100GB per file
([File Size Limits](https://...)).

**Aspera Desktop Client:** For larger files or batch uploads, install the Aspera Connect plugin
([Installation Guide](https://...)). This provides faster transfer speeds using Aspera's FASP protocol
([Transfer Technology](https://...)).

**Sources:**
- Aspera Upload Guide - https://...
- File Size Limits - https://...
- Installation Guide - https://...
```

---

**Remember:** Your goal is comprehensive, accurate answers through deep documentation exploration, not
surface-level responses. Always discover current documentation dynamically via `list_resources`.
"""

        tool_name: str = "ibm_document_search"
        if config:
            name_or_id = config.get("name") or config.get("id")
            if name_or_id and isinstance(name_or_id, str):
                tool_name = name_or_id

        super().__init__(
            name=tool_name,
            description=description,
            parameters=parameters,
        )

        # Initialize private attributes
        self._resource_manager = None

        if config:
            resource_manager = (
                config.get("resource_manager") if isinstance(config, dict)
                else getattr(config, "resource_manager", None) if hasattr(config, "resource_manager") else None
            )
            if resource_manager:
                self._resource_manager = resource_manager
                logger.info("IBM Document Search Tool configured with resource manager integration")

        logger.info("IBM Document Search Tool '%s' initialized", tool_name)

    @staticmethod
    def _is_valid_http_url(uri: str) -> bool:
        """Check if URI is a valid HTTP/HTTPS URL."""
        if not uri or not isinstance(uri, str):
            return False
        return uri.lower().strip().startswith(("http://", "https://"))

    async def _get_available_resources(self) -> List[Dict[str, Any]]:
        """Get available resources from resource manager, filtering for HTTP/HTTPS URLs only."""
        if not self._resource_manager:
            return []
        
        try:
            resource_list = await self._resource_manager.list_resources()
            resources = []
            
            for resource in resource_list:
                uri = str(getattr(resource, "uri", ""))
                if not self._is_valid_http_url(uri):
                    logger.debug("Filtered out non-HTTP resource: %s", getattr(resource, "name", "unknown"))
                    continue
                
                resources.append({
                    "name": getattr(resource, "name", ""),
                    "description": getattr(resource, "description", ""),
                    "uri": uri,
                    "mime_type": getattr(resource, "mime_type", ""),
                    "text": getattr(resource, "text", ""),
                    "tags": list(getattr(resource, "tags", [])) if hasattr(resource, "tags") else [],
                })

            logger.info("Retrieved %s valid HTTP/HTTPS resources (filtered from %s total)", len(resources), len(resource_list))
            return resources
        except Exception as e:
            logger.warning("Failed to retrieve resources from resource manager: %s", e)
            return []

    async def _search_resources(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search resources using tag-based matching."""
        try:
            max_results = min(max(1, max_results), 10)
            logger.info("Searching resources for: %s (max_results: %s)", query, max_results)

            available_resources = await self._get_available_resources()
            if not available_resources:
                logger.warning("No HTTP/HTTPS resources available to search")
                return []

            # Normalize query for case-insensitive search
            query_terms = set(query.lower().split())

            # Score and filter resources
            scored_resources = []
            for resource in available_resources:
                name = resource.get("name", "").lower()
                description = resource.get("description", "").lower()
                text = resource.get("text", "").lower()
                uri = resource.get("uri", "").lower()
                tags = set(tag.lower() for tag in resource.get("tags", []))

                score = 0
                # Tag matching (highest priority)
                exact_tag_matches = query_terms & tags
                score += len(exact_tag_matches) * 15
                for term in query_terms:
                    for tag in tags:
                        if term != tag and (term in tag or tag in term):
                            score += 8

                # Name matching
                query_str = " ".join(query_terms)
                if query_str in name:
                    score += 10
                elif all(term in name for term in query_terms):
                    score += 8
                elif any(term in name for term in query_terms):
                    score += 5

                # Description/text/uri matching
                for term in query_terms:
                    if term in description:
                        score += 3
                    if term in text:
                        score += 2
                    if term in uri:
                        score += 2

                if score > 0:
                    scored_resources.append((score, resource))

            scored_resources.sort(key=lambda x: x[0], reverse=True)
            results = [{
                "title": r.get("name", "Unknown Resource"),
                "url": r.get("uri", ""),
                "snippet": r.get("description") or r.get("text", "")[:200],
                "mime_type": r.get("mime_type", ""),
                "tags": r.get("tags", []),
                "relevance_score": score,
            } for score, r in scored_resources[:max_results]]

            logger.info("Found %s matching HTTP/HTTPS resources", len(results))
            return results
        except Exception as e:
            logger.error("Error searching resources: %s", e)
            return []

    def _match_resources_by_tags(
        self, question: str, available_resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Match resources to a question using tag-based matching."""
        if not available_resources:
            return []

        question_terms = set(question.lower().split())
        scored = []
        
        for resource in available_resources:
            tags = set(tag.lower() for tag in resource.get("tags", []))
            name = resource.get("name", "").lower()
            description = resource.get("description", "").lower()
            text = resource.get("text", "").lower()

            score = len(question_terms & tags) * 10  # Exact tag matches
            for term in question_terms:
                for tag in tags:
                    if term != tag and (term in tag or tag in term):
                        score += 5
                if term in name:
                    score += 3
                if term in description:
                    score += 1
                if term in text:
                    score += 1

            if score > 0:
                scored.append((score, resource))

        scored.sort(key=lambda x: x[0], reverse=True)
        matched = [r for _, r in scored]
        
        if matched:
            logger.info("Tag-based matching found %s relevant resources", len(matched))
        return matched


    async def _generate_stage_guidance(
        self, params: IBMDocumentSearchInput, available_resources: List[Dict[str, Any]]
    ) -> str:
        """
        Generate concise guidance for the current document search stage.

        Args:
            params: Validated input parameters
            available_resources: List of available HTTP/HTTPS resources

        Returns:
            Guidance text for the current stage
        """
        # Format resources info
        if available_resources:
            all_tags = {tag for r in available_resources for tag in r.get("tags", [])}
            resources_info = f"\n\n**Available Resources from MCP Server:**\n\n{self._format_resources_list(available_resources)}"
            if all_tags:
                resources_info += f"\n\n**💡 Tag-Based Matching:** Available tags: {', '.join(sorted(all_tags))}\n   Match these tags to keywords in your question for best results."
        else:
            resources_info = "\n\n**Note:** No HTTP/HTTPS resources currently available. Use other available tools to find documentation."

        question = params.question
        
        guidance = f"""**Document Search Guidance**

**Question:** {question}
**Current Stage:** {params.stage}

**Your Task:**
1. Call `list_resources` to discover available IBM documentation
2. **Match resources using tags:** Compare question keywords with resource tags
3. Filter for HTTP/HTTPS URLs only (ignore resource://, file://, etc.)
4. **Check which tools you have available** and use them to retrieve documentation:
   - If `url` tool is available: Use it to fetch pages directly
   - Otherwise: Use `web_search` to find pages, then `web_fetch` to retrieve them
5. Follow links within documentation for complete answers
6. Provide answer with inline citations: ([Page Title](URL))

{resources_info}

**Remember:**
- Use tag-based matching to find the most relevant documentation
- Check which tools are available before attempting to fetch pages
- Every fact needs a citation
- Use only IBM documentation from list_resources
- Follow links for comprehensive answers (3-5 pages typical)
- Stay within IBM documentation domains"""

        if params.sub_questions:
            guidance += f"\n\n**Your Sub-questions:**\n" + "\n".join(f"  {i+1}. {q}" for i, q in enumerate(params.sub_questions))
        if params.sources_count is not None:
            guidance += f"\n\n**Sources Found So Far:** {params.sources_count}"
        if params.gaps:
            guidance += "\n\n**Information Gaps:**\n" + "\n".join(f"  - {g}" for g in params.gaps)
        
        return guidance

    def _format_resources_list(self, resources: List[Dict[str, Any]]) -> str:
        """Format resources list for display with emphasis on tags."""
        if not resources:
            return "No HTTP/HTTPS resources available."

        formatted = []
        for i, r in enumerate(resources, 1):
            parts = [f"{i}. **{r.get('name', 'Unknown')}**"]
            if uri := r.get("uri"):
                parts.append(f"   URI: {uri}")
            if tags := r.get("tags"):
                parts.append(f"   Tags: {', '.join(tags)}")
                parts.append("   💡 Match these tags to your question for best results")
            desc = r.get("description") or (r.get("text", "")[:150] + "..." if len(r.get("text", "")) > 150 else r.get("text", ""))
            if desc:
                parts.append(f"   Description: {desc}")
            if mime := r.get("mime_type"):
                parts.append(f"   MIME Type: {mime}")
            formatted.append("\n".join(parts))
        return "\n\n".join(formatted)

    @staticmethod
    def _extract_json_from_string(text: str) -> Dict[str, Any]:
        """Extract JSON object from string that may contain text before JSON."""
        if not isinstance(text, str):
            raise ValueError("Input must be a string")
        
        # Find the last '{' that likely starts a JSON object
        start_idx = text.rfind('{')
        if start_idx == -1:
            raise ValueError("No JSON object found in string")
        
        # Extract JSON substring and find balanced braces
        json_str = text[start_idx:]
        brace_count = 0
        end_idx = len(json_str)
        
        for i, char in enumerate(json_str):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        # Try to parse the balanced JSON
        try:
            return json.loads(json_str[:end_idx])
        except json.JSONDecodeError:
            # Fallback: try regex to find any JSON-like structure
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Could not extract valid JSON from string")

    @staticmethod
    def _extract_question_from_args(arguments: Dict[str, Any]) -> str:
        """Extract question from arguments."""
        question = arguments.get("question") or arguments.get("search_query")
        return question.strip() if question and isinstance(question, str) else "Unknown question"

    def _handle_validation_error(
        self, error: ValidationError, raw_arguments: Dict[str, Any]
    ) -> ToolResult:
        """
        Handle Pydantic validation errors gracefully.

        Args:
            error: Pydantic validation error
            raw_arguments: Original arguments that failed validation

        Returns:
            ToolResult with error information
        """
        logger.error("Validation error in IBM document search: %s", error)

        question = self._extract_question_from_args(raw_arguments)

        error_response = {
            "stage": "error",
            "question": question,
            "guidance": f"Validation Error: {str(error)}",
            "nextStage": None,
            "status": "validation_error",
            "error": str(error),
            "validation_errors": error.errors(),
        }

        return ToolResult(
            content=[
                TextContent(type="text", text=json.dumps(error_response, indent=2))
            ]
        )

    async def run(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute the IBM document search tool.

        Args:
            arguments: Tool arguments containing document search parameters

        Returns:
            ToolResult: Document search guidance for the current stage
        """
        logger.info("IBM document search tool run called with arguments: %s", arguments)

        try:
            # Handle case where arguments might be a string with text before JSON
            if isinstance(arguments, str):
                logger.debug("Arguments received as string, attempting to extract JSON")
                try:
                    arguments = IBMDocumentSearchTool._extract_json_from_string(arguments)
                except ValueError as e:
                    logger.error("Failed to extract JSON from string arguments: %s", e)
                    # Fallback: create minimal valid arguments from the string
                    arg_str = str(arguments)
                    question_text = arg_str[:200] if len(arg_str) > 200 else arg_str
                    arguments = {"question": question_text}
            
            # Clean argument values that might contain mixed content
            cleaned_args = {}
            for key, value in arguments.items():
                if isinstance(value, str) and '{' in value:
                    if not value.strip().startswith('{'):
                        try:
                            cleaned_args[key] = IBMDocumentSearchTool._extract_json_from_string(value)
                        except (ValueError, json.JSONDecodeError):
                            cleaned_args[key] = value
                    else:
                        try:
                            cleaned_args[key] = json.loads(value)
                        except json.JSONDecodeError:
                            cleaned_args[key] = value
                else:
                    cleaned_args[key] = value
            
            params = IBMDocumentSearchInput(**cleaned_args)

            # Get available resources (filtered for HTTP/HTTPS only)
            available_resources = await self._get_available_resources()
            logger.info("Available HTTP/HTTPS resources: %s", len(available_resources))

            question = params.question

            # Generate guidance for the current stage
            guidance = await self._generate_stage_guidance(params, available_resources)

            # Add additional context if provided
            if params.additional_context:
                guidance += f"\n\n**Additional Context:** {params.additional_context}"

            # Determine next stage
            stage_flow = {
                "planning": "citation",
                "citation": "summarization",
                "summarization": "complete",
                "complete": None,
            }
            next_stage = stage_flow.get(params.stage, "citation")

            # Create simplified response
            response = {
                "stage": params.stage,
                "question": question,
                "guidance": guidance,
                "nextStage": next_stage,
                "availableResources": len(available_resources),
                "status": "success",
            }

            # Add search query hint if provided
            if params.search_query:
                response["suggestedSearchQuery"] = params.search_query

            question_display = question[:50] + "..." if len(question) > 50 else question
            logger.info(
                "IBM document search guidance provided - Stage: %s, Question: %s",
                params.stage,
                question_display,
            )

            response = ToolResult(
                content=[TextContent(type="text", text=json.dumps(response, indent=2))]
            )
            logger.debug("IBM document search tool response: %s", response)
            return response
        except ValidationError as e:
            return self._handle_validation_error(e, arguments)

        except Exception as e:
            logger.error("Unexpected error in IBM document search: %s", e)

            question = self._extract_question_from_args(arguments)

            error_response = {
                "stage": "error",
                "question": question,
                "guidance": f"An unexpected error occurred: {str(e)}",
                "nextStage": None,
                "status": "failed",
                "error": str(e),
            }

            return ToolResult(
                content=[
                    TextContent(type="text", text=json.dumps(error_response, indent=2))
                ]
            )
