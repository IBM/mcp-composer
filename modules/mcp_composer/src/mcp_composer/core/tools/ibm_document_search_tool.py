# ibm_document_search_tool.py

import json
from typing import Dict, Any, Optional, List, Literal

from fastmcp.tools import Tool
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from pydantic import BaseModel, Field, ConfigDict, PrivateAttr, ValidationError

from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


class IBMDocumentSearchInput(BaseModel):
    """Input parameters for IBM Document Search Tool"""

    model_config = ConfigDict(extra="forbid")

    question: Optional[str] = Field(
        None,
        description="Main research question to investigate. Optional - if not provided, will be derived from search_query, sub_questions, or use a default.",
        min_length=1
    )

    stage: Literal["planning", "citation", "summarization", "complete"] = Field(
        default="complete",
        description="Current research stage you're working on."
    )

    sub_questions: Optional[List[str]] = Field(
        None,
        description="List of sub-questions you've identified (for planning stage). Used to provide context for guidance."
    )

    sources_count: Optional[int] = Field(
        None,
        ge=0,
        description="Optional count of sources found so far. Used to provide context-aware guidance."
    )

    gaps: Optional[List[str]] = Field(
        None,
        description="Optional list of information gaps identified. Used to provide context-aware guidance."
    )

    additional_context: Optional[str] = Field(
        None,
        description="Extra guidance or constraints for the research."
    )

    search_query: Optional[str] = Field(
        None,
        description="Optional suggested search query. This is a hint for the agent to use when searching available resources or using the url tool. The tool does not perform automatic searches - the agent should use the url tool to fetch documentation pages.",
        min_length=1
    )

    max_results: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Optional hint for maximum number of results to consider (default: 5, max: 10). This is guidance only - actual search behavior depends on the tools the agent uses."
    )


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

When you call `list_resources`, each resource includes tags that describe its content. Match these tags to keywords in the user's question to find the most relevant documentation.

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
  - Extract the domain from the resource URL (e.g., if resource is `https://cloud.ibm.com/docs/watsonxdata`, search within `cloud.ibm.com`)
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
IBM Instana provides real-time monitoring with 1-second granularity ([Instana Overview](https://www.ibm.com/docs/...)) and supports over 250 technologies ([Supported Technologies](https://www.ibm.com/docs/...)).
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

**Web Browser Upload:** Navigate to your workspace and use the drag-and-drop interface ([Aspera Upload Guide](https://...)). This supports files up to 100GB per file ([File Size Limits](https://...)).

**Aspera Desktop Client:** For larger files or batch uploads, install the Aspera Connect plugin ([Installation Guide](https://...)). This provides faster transfer speeds using Aspera's FASP protocol ([Transfer Technology](https://...)).

**Sources:**
- Aspera Upload Guide - https://...
- File Size Limits - https://...
- Installation Guide - https://...
```

---

**Remember:** Your goal is comprehensive, accurate answers through deep documentation exploration, not surface-level responses. Always discover current documentation dynamically via `list_resources`.
"""

        # Get tool name from config or use default
        tool_name = "ibm_document_search"
        if config and "name" in config:
            tool_name = config["name"]
        elif config and "id" in config:
            tool_name = config["id"]

        super().__init__(
            name=tool_name,
            description=description,
            parameters=parameters,
        )

        # Initialize private attributes
        self._resource_manager = None

        if config:
            potential_resource_manager = None
            if isinstance(config, dict):
                potential_resource_manager = config.get("resource_manager")
            elif hasattr(config, "resource_manager"):
                potential_resource_manager = getattr(config, "resource_manager")

            if potential_resource_manager is not None:
                self._resource_manager = potential_resource_manager
                logger.info("IBM Document Search Tool configured with resource manager integration")

        logger.info(f"IBM Document Search Tool '{tool_name}' initialized")

    def _is_valid_http_url(self, uri: str) -> bool:
        """
        Check if a URI is a valid HTTP/HTTPS URL.
        
        Args:
            uri: The URI to check
            
        Returns:
            True if URI starts with http:// or https://, False otherwise
        """
        if not uri or not isinstance(uri, str):
            return False
        uri_lower = uri.lower().strip()
        return uri_lower.startswith('http://') or uri_lower.startswith('https://')

    async def _get_available_resources(self) -> List[Dict[str, Any]]:
        """
        Get available resources from the resource manager, filtering for valid HTTP/HTTPS URLs only.
        
        Returns:
            List of available resources with name, description, uri, and mime_type (HTTP/HTTPS only)
        """
        resources = []
        if self._resource_manager:
            try:
                resource_list = await self._resource_manager.list_resources()
                for resource in resource_list:
                    uri = str(getattr(resource, "uri", ""))

                    # Filter: only include resources with valid HTTP/HTTPS URLs
                    if self._is_valid_http_url(uri):
                        resources.append({
                            "name": getattr(resource, "name", ""),
                            "description": getattr(resource, "description", ""),
                            "uri": uri,
                            "mime_type": getattr(resource, "mime_type", ""),
                            "tags": list(getattr(resource, "tags", [])) if hasattr(resource, "tags") else [],
                            "text": getattr(resource, "text", "")
                        })
                    else:
                        logger.debug(f"Filtered out non-HTTP resource: {getattr(resource, 'name', 'unknown')} with URI: {uri}")

                logger.info(f"Retrieved {len(resources)} valid HTTP/HTTPS resources from resource manager (filtered from {len(resource_list)} total)")
            except Exception as e:
                logger.warning(f"Failed to retrieve resources from resource manager: {e}")
        return resources

    async def _search_resources(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search within available resources to suggest which ones to fetch.
        Uses tag-based matching for intelligent resource selection.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 5, max: 10)
            
        Returns:
            List of suggested resources to fetch with name, uri, description, and relevance score
        """
        try:
            max_results = min(max(1, max_results), 10)  # Clamp between 1 and 10
            logger.info(f"Searching resources for: {query} (max_results: {max_results})")

            # Get available resources (already filtered for HTTP/HTTPS)
            available_resources = await self._get_available_resources()

            if not available_resources:
                logger.warning("No HTTP/HTTPS resources available to search")
                return []

            # Normalize query for case-insensitive search
            query_lower = query.lower()
            query_terms = query_lower.split()

            # Score and filter resources based on query match
            scored_resources = []
            for resource in available_resources:
                name = resource.get("name", "").lower()
                description = resource.get("description", "").lower()
                text = resource.get("text", "").lower()
                uri = resource.get("uri", "").lower()
                tags = [tag.lower() for tag in resource.get("tags", [])]

                # Calculate relevance score
                score = 0

                # TAG MATCHING (Highest Priority) - NEW!
                # Exact tag match is the most reliable indicator
                for term in query_terms:
                    for tag in tags:
                        if term == tag:
                            score += 15  # Exact tag match - highest priority
                        elif term in tag or tag in term:
                            score += 8   # Partial tag match - high priority

                # Exact match in name
                if query_lower in name:
                    score += 10

                # All query terms in name
                if all(term in name for term in query_terms):
                    score += 8

                # Query terms in description or text
                for term in query_terms:
                    if term in description:
                        score += 3
                    if term in text:
                        score += 2
                    if term in uri:
                        score += 2

                # Partial match in name
                if any(term in name for term in query_terms):
                    score += 5

                if score > 0:
                    scored_resources.append((score, resource))

            # Sort by score (descending) and take top results
            scored_resources.sort(key=lambda x: x[0], reverse=True)
            results = []

            for score, resource in scored_resources[:max_results]:
                results.append({
                    "title": resource.get("name", "Unknown Resource"),
                    "url": resource.get("uri", ""),
                    "snippet": resource.get("description", "") or resource.get("text", "")[:200],
                    "mime_type": resource.get("mime_type", ""),
                    "tags": resource.get("tags", []),
                    "relevance_score": score
                })

            logger.info(f"Found {len(results)} matching HTTP/HTTPS resources (tag-based matching)")
            return results

        except Exception as e:
            logger.error(f"Error searching resources: {e}")
            return []

    def _match_resources_by_tags(
        self,
        question: str,
        available_resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Match resources to a question using tag-based matching.
        
        Args:
            question: The user's question
            available_resources: List of available resources with tags
            
        Returns:
            List of resources sorted by relevance (tag matches)
        """
        if not available_resources:
            return []

        # Extract keywords from question
        question_lower = question.lower()
        question_terms = set(question_lower.split())

        # Score each resource based on tag matches
        scored = []
        for resource in available_resources:
            tags = [tag.lower() for tag in resource.get("tags", [])]
            name = resource.get("name", "").lower()
            description = resource.get("description", "").lower()
            text = resource.get("text", "").lower()

            score = 0

            # Tag matching (highest priority)
            for term in question_terms:
                for tag in tags:
                    if term == tag:
                        score += 10  # Exact match
                    elif term in tag or tag in term:
                        score += 5   # Partial match

            # Name matching
            for term in question_terms:
                if term in name:
                    score += 3

            # Description/text matching
            for term in question_terms:
                if term in description:
                    score += 1
                if term in text:
                    score += 1

            if score > 0:
                scored.append((score, resource))

        # Sort by score (descending)
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return sorted resources
        matched = [resource for _, resource in scored]

        if matched:
            logger.info(f"Tag-based matching found {len(matched)} relevant resources")

        return matched

    def _derive_question_from_params(self, params: IBMDocumentSearchInput) -> str:
        """
        Derive a question from the input parameters if not provided directly.
        
        Args:
            params: Validated input parameters
            
        Returns:
            Derived or default question string
        """
        # Try search_query first
        if params.search_query:
            logger.info(f"Using search_query as question: {params.search_query}")
            return params.search_query

        # Try first sub-question
        if params.sub_questions and len(params.sub_questions) > 0:
            derived = f"Research question related to: {params.sub_questions[0]}"
            logger.info(f"Derived question from sub_questions: {derived}")
            return derived

        # Default fallback
        logger.warning("No question or search_query provided, using default question")
        return "General IBM documentation search"

    async def _generate_stage_guidance(
        self,
        params: IBMDocumentSearchInput,
        available_resources: List[Dict[str, Any]]
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
            resources_list_text = self._format_resources_list(available_resources)

            # Get unique tags from all resources
            all_tags = set()
            for resource in available_resources:
                all_tags.update(resource.get("tags", []))

            tags_summary = f"Available tags: {', '.join(sorted(all_tags))}" if all_tags else ""

            resources_info = f"\n\n**Available Resources from MCP Server:**\n\n{resources_list_text}"
            if tags_summary:
                resources_info += f"\n\n**💡 Tag-Based Matching:** {tags_summary}"
                resources_info += "\n   Match these tags to keywords in your question for best results."
        else:
            resources_info = "\n\n**Note:** No HTTP/HTTPS resources currently available. Use other available tools to find documentation."

        # Get the actual question (derived if necessary)
        question = params.question or self._derive_question_from_params(params)

        # Base guidance - simple and unified
        base_guidance = f"""**Document Search Guidance**

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
- Stay within IBM documentation domains
"""

        # Add context if provided
        if params.sub_questions:
            sub_q_list = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(params.sub_questions))
            base_guidance += f"\n**Your Sub-questions:**\n{sub_q_list}\n"

        if params.sources_count is not None:
            base_guidance += f"\n**Sources Found So Far:** {params.sources_count}\n"

        if params.gaps:
            gaps_list = "\n".join(f"  - {g}" for g in params.gaps)
            base_guidance += f"\n**Information Gaps:**\n{gaps_list}\n"

        return base_guidance

    def _format_resources_list(self, resources: List[Dict[str, Any]]) -> str:
        """Format the list of available resources for display with emphasis on tags"""
        if not resources:
            return "No HTTP/HTTPS resources available."

        formatted = []
        for i, resource in enumerate(resources, 1):
            name = resource.get("name", "Unknown")
            description = resource.get("description", "")
            text = resource.get("text", "")
            uri = resource.get("uri", "")
            mime_type = resource.get("mime_type", "")
            tags = resource.get("tags", [])

            resource_str = f"{i}. **{name}**"
            if uri:
                resource_str += f"\n   URI: {uri}"

            # Show tags prominently for matching
            if tags:
                resource_str += f"\n   Tags: {', '.join(tags)}"
                resource_str += "\n   💡 Match these tags to your question for best results"

            if description:
                resource_str += f"\n   Description: {description}"
            elif text:
                # Use text as description if description is empty
                text_preview = text[:150] + "..." if len(text) > 150 else text
                resource_str += f"\n   Description: {text_preview}"

            if mime_type:
                resource_str += f"\n   MIME Type: {mime_type}"

            formatted.append(resource_str)

        return "\n\n".join(formatted)

    def _handle_validation_error(
        self,
        error: ValidationError,
        raw_arguments: Dict[str, Any]
    ) -> ToolResult:
        """
        Handle Pydantic validation errors gracefully.
        
        Args:
            error: Pydantic validation error
            raw_arguments: Original arguments that failed validation
            
        Returns:
            ToolResult with error information
        """
        logger.error(f"Validation error in IBM document search: {error}")

        # Try to extract question from raw arguments
        question = (
            raw_arguments.get("question") or
            raw_arguments.get("Question") or
            raw_arguments.get("mainQuestion") or
            raw_arguments.get("main_question") or
            raw_arguments.get("search_query") or
            raw_arguments.get("searchQuery") or
            "Unknown question"
        )

        if isinstance(question, str):
            question = question.strip()

        error_response = {
            "stage": "error",
            "question": question,
            "guidance": f"Validation Error: {str(error)}",
            "nextStage": None,
            "status": "validation_error",
            "error": str(error),
            "validation_errors": error.errors()
        }

        return ToolResult(content=[TextContent(type="text", text=json.dumps(error_response, indent=2))])

    async def run(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute the IBM document search tool.
        
        Args:
            arguments: Tool arguments containing document search parameters
            
        Returns:
            ToolResult: Document search guidance for the current stage
        """
        logger.info(f"IBM document search tool run called with arguments: {arguments}")

        try:
            # Validate and parse arguments with Pydantic
            # Handle both camelCase and snake_case by normalizing
            normalized_args = {}
            for key, value in arguments.items():
                # Convert camelCase to snake_case for common parameters
                if key == "mainQuestion":
                    normalized_args["question"] = value
                elif key == "searchQuery":
                    normalized_args["search_query"] = value
                elif key == "subQuestions":
                    normalized_args["sub_questions"] = value
                elif key == "sourcesCount":
                    normalized_args["sources_count"] = value
                elif key == "maxResults":
                    normalized_args["max_results"] = value
                elif key == "additionalContext":
                    normalized_args["additional_context"] = value
                else:
                    normalized_args[key] = value

            # Validate with Pydantic - this gives us type safety and automatic validation
            params = IBMDocumentSearchInput(**normalized_args)

            # Get available resources (filtered for HTTP/HTTPS only)
            available_resources = await self._get_available_resources()
            logger.info(f"Available HTTP/HTTPS resources: {len(available_resources)}")

            # Derive question if not provided
            question = params.question or self._derive_question_from_params(params)

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
                "complete": None
            }
            next_stage = stage_flow.get(params.stage, "citation")

            # Create simplified response
            response = {
                "stage": params.stage,
                "question": question,
                "guidance": guidance,
                "nextStage": next_stage,
                "availableResources": len(available_resources),
                "status": "success"
            }

            # Add search query hint if provided
            if params.search_query:
                response["suggestedSearchQuery"] = params.search_query

            question_display = question[:50] + "..." if len(question) > 50 else question
            logger.info(f"IBM document search guidance provided - Stage: {params.stage}, Question: {question_display}")

            response = ToolResult(content=[TextContent(type="text", text=json.dumps(response, indent=2))])
            logger.debug(f"IBM document search tool response: {response}")
            return response
        except ValidationError as e:
            return self._handle_validation_error(e, arguments)

        except Exception as e:
            logger.error(f"Unexpected error in IBM document search: {e}")

            # Try to extract question from raw arguments
            question = (
                arguments.get("question") or
                arguments.get("Question") or
                arguments.get("mainQuestion") or
                arguments.get("main_question") or
                arguments.get("search_query") or
                arguments.get("searchQuery") or
                "Unknown question"
            )

            if isinstance(question, str):
                question = question.strip()

            error_response = {
                "stage": "error",
                "question": question,
                "guidance": f"An unexpected error occurred: {str(e)}",
                "nextStage": None,
                "status": "failed",
                "error": str(e)
            }

            return ToolResult(content=[TextContent(type="text", text=json.dumps(error_response, indent=2))])
