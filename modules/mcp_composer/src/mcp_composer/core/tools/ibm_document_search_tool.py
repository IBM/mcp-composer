# ibm_document_search_tool.py

import json
from typing import Dict, Any, Optional, List

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS = None
    DDGS_AVAILABLE = False

from fastmcp.tools import Tool
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from pydantic import ConfigDict, PrivateAttr

from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


class IBMDocumentSearchSchema:
    """IBM Document Search Tool parameter schema definition"""

    @staticmethod
    def get_schema() -> Dict[str, Any]:
        """Get the parameter schema for IBM Document Search Tool"""
        return {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Main research question to investigate. Optional - if not provided, will be derived from search_query, sub_questions, or use a default.",
                    "minLength": 1
                },
                "stage": {
                    "type": "string",
                    "description": "Current research stage you're working on.",
                    "enum": [
                        "planning",
                        "citation",
                        "summarization",
                        "complete"
                    ],
                    "default": "complete"
                },
                "sub_questions": {
                    "type": "array",
                    "description": "List of sub-questions you've identified (for planning stage). Used to provide context for guidance.",
                    "items": {
                        "type": "string"
                    }
                },
                "sources_count": {
                    "type": "integer",
                    "description": "Optional count of sources found so far. Used to provide context-aware guidance.",
                    "minimum": 0
                },
                "gaps": {
                    "type": "array",
                    "description": "Optional list of information gaps identified. Used to provide context-aware guidance.",
                    "items": {
                        "type": "string"
                    }
                },
                "additional_context": {
                    "type": "string",
                    "description": "Extra guidance or constraints for the research."
                },
                "search_query": {
                    "type": "string",
                    "description": "Optional suggested search query. This is a hint for the agent to use when searching available resources or using URL tools. The tool does not perform automatic searches - the agent should use available MCP server tools or URL tools to perform actual searches.",
                    "minLength": 1
                },
                "max_results": {
                    "type": "integer",
                    "description": "Optional hint for maximum number of results to consider (default: 5, max: 10). This is guidance only - actual search behavior depends on the tools the agent uses.",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5
                }
            },
            "required": [],
            "additionalProperties": False
        }


def load_ibm_document_search_schema() -> Dict[str, Any]:
    """Load the IBM document search tool parameter schema"""
    return IBMDocumentSearchSchema.get_schema()


class IBMDocumentSearchTool(Tool):
    """
    IBM Document Search Tool for finding accurate and well-supported answers.
    
    This tool guides you through a structured 3-stage document search workflow to perform
    documentation-focused searches by systematically breaking down questions into
    2-3 sub-questions, finding relevant sources from resources available in conencted mcp servers,
    and synthesizing accurate summaries with proper citations.
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

        # Load parameters from schema class
        parameters = load_ibm_document_search_schema()

        # Comprehensive system prompt that guides the agent
        description = """
        A strict IBM Documentation Search Agent. This tool retrieves, analyzes, and summarizes
        information EXCLUSIVELY from IBM documentation resources made available through
        the MCP server (via list_resources() and resource search queries).

        The tool must always operate using three sequential stages:

        -------------------------------------------------------------------
        1. PLANNING STAGE (stage="planning")
        -------------------------------------------------------------------
        - Restate the user’s question.
        - Break the question into 2–3 precise, factual, non-overlapping sub-questions.
        - No assumptions, no inference, no external knowledge.
        - Output fields:
            - question
            - sub_questions
            - stage="planning"

        -------------------------------------------------------------------
        2. CITATION STAGE (stage="citation")
        -------------------------------------------------------------------
        - Use search tools (list_resources(), search_query) to locate relevant resources.
        - For EACH sub-question, return ALL relevant sources including:
            - Title
            - URL
            - Summary of relevance
            - Relevant content excerpts
        - ONLY use documentation provided through  server as resources or url tools.
        - Output fields:
            - question
            - sub_questions
            - sources
            - stage="citation"

        -------------------------------------------------------------------
        3. SUMMARIZATION STAGE (stage="summarization")
        -------------------------------------------------------------------
        - Provide summaries using ONLY verifiable information from cited sources.
        - EVERY factual statement MUST include an inline citation.
        - If something is missing from documentation, respond with:
                "This information is not available in the provided documentation."
        - No assumptions, no general knowledge, no inferred details.
        - Output fields:
            - question
            - findings
            - sources
            - stage="summarization"

        -------------------------------------------------------------------
        HARD COMPLIANCE RULES (MANDATORY)
        -------------------------------------------------------------------
        - Do NOT use general knowledge.
        - Do NOT infer or guess missing information.
        - Do NOT synthesize information from undocumented IBM content.
        - Do NOT use URLs or documentation not provided through MCP.
        - Do NOT include opinions or speculation.
        - Do NOT include uncited factual statements.
        - Do NOT bypass the 3-stage structure.

        - Only use documented content from the resources accessible via:
                list_resources()
                search_query
        - Every factual statement must contain a citation.
        - If you cannot cite it, you cannot say it.

        -------------------------------------------------------------------
        REQUIRED RESPONSE FORMAT
        -------------------------------------------------------------------
        Each tool invocation MUST include these fields depending on stage:

        - question:         The main user query.
        - stage:            One of: "planning", "citation", "summarization", "complete"
        - sub_questions:    (planning stage)
        - search_query:     (optional for citation)
        - max_results:      (optional)
        - sources:          (citation stage)
        - findings:         (summarization stage)
        - additional_context: (optional)

        -------------------------------------------------------------------
        FAILURE MODE REQUIREMENT
        -------------------------------------------------------------------
        If required information does not appear in the provided documentation,
        the assistant MUST reply:

      "I can only provide verified information based on the IBM documentation.
       The information you requested is not available in the provided documentation."

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

    async def _get_available_resources(self) -> List[Dict[str, Any]]:
        """
        Get available resources from the resource manager.
        
        Returns:
            List of available resources with name, description, uri, and mime_type
        """
        resources = []
        if self._resource_manager:
            try:
                resource_list = await self._resource_manager.list_resources()
                for resource in resource_list:
                    resources.append({
                        "name": getattr(resource, "name", ""),
                        "description": getattr(resource, "description", ""),
                        "uri": str(getattr(resource, "uri", "")),
                        "mime_type": getattr(resource, "mime_type", ""),
                        "tags": list(getattr(resource, "tags", [])) if hasattr(resource, "tags") else []
                    })
                logger.info(f"Retrieved {len(resources)} available resources from resource manager")
            except Exception as e:
                logger.warning(f"Failed to retrieve resources from resource manager: {e}")
        return resources

    async def _search_resources(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search within available resources only.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 5, max: 10)
            
        Returns:
            List of matching resources with name, uri, description, and mime_type
        """
        try:
            max_results = min(max(1, max_results), 10)  # Clamp between 1 and 10
            logger.info(f"Searching resources for: {query} (max_results: {max_results})")

            # Get available resources
            available_resources = await self._get_available_resources()

            if not available_resources:
                logger.warning("No resources available to search")
                return []

            # Normalize query for case-insensitive search
            query_lower = query.lower()
            query_terms = query_lower.split()

            # Score and filter resources based on query match
            scored_resources = []
            for resource in available_resources:
                name = resource.get("name", "").lower()
                description = resource.get("description", "").lower()
                uri = resource.get("uri", "").lower()
                tags = [tag.lower() for tag in resource.get("tags", [])]

                # Calculate relevance score
                score = 0

                # Exact match in name (highest priority)
                if query_lower in name:
                    score += 10

                # All query terms in name
                if all(term in name for term in query_terms):
                    score += 8

                # Query terms in description
                for term in query_terms:
                    if term in description:
                        score += 3
                    if term in uri:
                        score += 2
                    if any(term in tag for tag in tags):
                        score += 2

                # Partial match in name
                if any(term in name for term in query_terms):
                    score += 5

                if score > 0:
                    scored_resources.append((score, resource))

            # Sort by score (descending) and take top results
            scored_resources.sort(key=lambda x: x[0], reverse=True)
            results = [resource for _, resource in scored_resources[:max_results]]

            # Format results to match expected structure
            formatted_results = []
            for resource in results:
                formatted_results.append({
                    "title": resource.get("name", "Unknown Resource"),
                    "url": resource.get("uri", ""),
                    "snippet": resource.get("description", ""),
                    "mime_type": resource.get("mime_type", ""),
                    "tags": resource.get("tags", [])
                })

            logger.info(f"Found {len(formatted_results)} matching resources")
            return formatted_results

        except Exception as e:
            logger.error(f"Error searching resources: {e}")
            return []

    async def _generate_stage_guidance(self, stage: str, question: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate guidance for a specific document search stage"""

        # Get available resources
        available_resources = await self._get_available_resources()
        resources_list_text = self._format_resources_list(available_resources) if available_resources else "No resources available. Use web search or other available tools to find sources."

        guidance = {
            "planning": f"""**STAGE 1: PLANNING**

**Main Question:** {question}

**Your task:** Break down the user's question into 2–3 precise, self-contained sub-questions that together address the user's query completely.

**Guidelines:**
- Carefully analyze the user's main question
- Identify key aspects, dimensions, or unknowns that need to be explored
- Formulate 2–3 sub-questions that are clear, factual, and non-overlapping
- Ensure each sub-question could independently be answered by a search
- Stay within the context of IBM Instana Observability documentation

**Response format:**
```markdown
**Main Question:** <restate the user's question>

**Subquestions:**

1. ...
2. ...
3. ...
```

**Next steps:**
1. Generate your list of 2-3 sub-questions
2. Review them to ensure comprehensive coverage
3. Once satisfied, move to Stage 2: Citation""",

            "citation": f"""**STAGE 2: CITATION**

**Your task:** For each sub-question, find the most relevant sources using the available resources and URL tools.

**CRITICAL RULES:**
- **ONLY use sources from the provided IBM Instana Observability documentation**
- **Use available resources from list_resources() - see list below**
- **Use URL tools to fetch content from resource URIs**
- **Use available search tools from connected MCP servers for additional searches**
- **Do NOT use general knowledge, common patterns, or logical inferences**
- **Do NOT synthesize information from general knowledge about IBM products**
- If you cannot find a source in the documentation, state: "No source found in the provided documentation"

**Available Resources:**
{resources_list_text}

**Guidelines:**
- **First, review the available resources listed above** - these are documentation sources you can access
- **Use URL tools to fetch the actual content from resource URIs** - don't just list them
- **Use search tools from connected MCP servers** to find additional relevant documentation
- Use the entire sub-question or a focused search term when retrieving sources
- Select the most authoritative and relevant materials from the IBM Instana Observability documentation ONLY
- Always stay within the context of the provided website or documentation
- Do not make assumptions or generate content not supported by the source material
- For each source, extract: Title, URL, Short summary of relevance, Full content (or excerpt)
- If a source doesn't exist in the documentation, do NOT create or infer information

**Response format:**
```markdown
### Subquestion: ...

**Sources:**

1. **Title:** ...
   - **URL:** ...
   - **Summary:** ...
   - **Content:** ...

2. ...
```

**For each sub-question:**
1. Review available resources and identify relevant URIs
2. Use URL tools to fetch content from those URIs
3. Use MCP server search tools if needed for additional searches
4. Review fetched content for relevance to IBM Instana documentation
5. Select the most relevant sources
6. Record source information in the required format

**Next steps:**
1. Use URL tools to fetch content from relevant resource URIs
2. Use MCP server search tools for additional searches if needed
3. Compile your source list with proper citations
4. Once you have sources for all sub-questions, move to Stage 3: Summarization""",

            "summarization": """**STAGE 3: SUMMARIZATION**

**Your task:** Synthesize information from the gathered sources into concise, accurate summaries that directly answer each sub-question.

**CRITICAL: CITATIONS ARE MANDATORY**
- **Every answer MUST include citations** - No information should be provided without citing the source
- **Every factual statement MUST be followed by a citation** in the format: "([Source Name/URL])"
- **Citations are required** - If you cannot cite a source, do not include that information
- **An answer without citations is incomplete and violates the guardrails**

**CRITICAL RULES:**
- **ONLY summarize information explicitly stated in the cited sources**
- **Do NOT add information from general knowledge or make logical inferences**
- **Do NOT synthesize from common patterns or prior knowledge about IBM products**
- **Every bullet point MUST be directly traceable to a specific cited source with URL**
- If a source doesn't contain the needed information, state: "This information is not available in the provided documentation"

**Guidelines:**
- Focus ONLY on information explicitly stated in the cited sources
- **ALWAYS cite the source** for each piece of information - use inline citations: "([Source Name/URL])"
- Summarize key insights from each source in 2–4 concise bullet points
- **Each bullet point must reference its source** - either inline or clearly linked
- Avoid redundancy and ensure factual neutrality
- Maintain an objective and evidence-based tone
- Ensure all claims are traceable to a specific cited source with URL
- Do NOT invent, infer, or synthesize information from general knowledge
- If information is missing, explicitly state: "This information could not be found in the provided documentation"

**Response format:**
```markdown
### Subquestion: ...

**Answer:**
[Your summary answer here. Every factual statement must include a citation like: "According to [Source Name/URL], ..." or "([Source Name/URL])"]

**Sources Cited:**
- **Source 1:** [Source Name] - [URL]
  - [Key point 1 from this source] ([Source Name/URL])
  - [Key point 2 from this source] ([Source Name/URL])
  - [Key point 3 from this source] ([Source Name/URL])

- **Source 2:** [Source Name] - [URL]
  - [Key point 1 from this source] ([Source Name/URL])
  - [Key point 2 from this source] ([Source Name/URL])
  - [Key point 3 from this source] ([Source Name/URL])
```

**For each sub-question:**
1. Review all sources for that sub-question
2. Extract relevant information from each source
3. **Write your answer with inline citations** for every factual statement
4. Summarize findings in 2-4 bullet points per source, each with citation
5. Ensure all information is traceable to cited sources with URLs

**Next steps:**
1. Summarize findings for each sub-question **with citations**
2. Ensure all sub-questions have summaries **with proper citations**
3. Verify all claims are properly cited with source names and URLs
4. Mark document search as complete""",

            "complete": """**DOCUMENT SEARCH COMPLETE**

Your document search has been completed through all 3 stages. Review your final response to ensure:
- All sub-questions are addressed (2-3 sub-questions)
- **EVERY answer includes citations** - No information without source citations
- Sources are properly cited with Title, URL, Summary, and Content
- **Every factual statement has an inline citation** in the format: "([Source Name/URL])"
- Summaries are factual and traceable to specific sources with URLs
- Information stays within IBM Instana Observability documentation scope ONLY
- NO general knowledge, inferences, or synthesized information from common patterns
- NO assumptions or unsupported content
- Every claim is directly traceable to a cited source with URL

**REQUIRED RESPONSE FORMAT WITH CITATIONS:**

Your final response MUST follow this format with citations:

```markdown
## Answer to: [Main Question]

### Sub-question 1: [Question text]

**Answer:**
[Your answer here with inline citations after EVERY factual statement. For example: "According to the IBM Instana documentation ([Source Name/URL]), feature X works by... ([Source Name/URL])"]

**Sources Cited:**
- **Source 1:** [Source Name] - [URL]
  - [Key point 1 from this source] ([Source Name/URL])
  - [Key point 2 from this source] ([Source Name/URL])
  - [Key point 3 from this source] ([Source Name/URL])

- **Source 2:** [Source Name] - [URL]
  - [Key point 1 from this source] ([Source Name/URL])
  - [Key point 2 from this source] ([Source Name/URL])

### Sub-question 2: [Question text]

**Answer:**
[Answer with citations...]

**Sources Cited:**
- **Source 1:** [Source Name] - [URL]
  - [Key points with citations...]

### Sub-question 3: [Question text]

**Answer:**
[Answer with citations...]

**Sources Cited:**
- **Source 1:** [Source Name] - [URL]
  - [Key points with citations...]

## Complete Sources List

1. **[Source Name]** - [URL]
   - Summary: [Brief summary]
   
2. **[Source Name]** - [URL]
   - Summary: [Brief summary]
```

**CRITICAL: CITATION EXAMPLES**

Every factual statement MUST include a citation. Examples:

- CORRECT: "IBM Instana provides real-time monitoring capabilities ([IBM Instana Documentation](https://example.com/doc))"
- CORRECT: "The system supports multiple data sources ([Source Name/URL])"
- WRONG: "IBM Instana provides real-time monitoring capabilities" (no citation)
- WRONG: "The system supports multiple data sources" (no citation)

**CRITICAL COMPLIANCE CHECK:**
Before finalizing, verify:
- **Did I include citations for EVERY factual statement?**
- **Does my answer have a "Sources Cited" section for each sub-question?**
- **Did I include a complete "Sources List" at the end?**
- Did I use ONLY information from the provided documentation?
- Did I avoid using general knowledge about IBM products?
- Did I avoid making logical inferences?
- Did I avoid synthesizing from common patterns?
- Can every claim be traced to a specific cited source with URL?

**CITATION REQUIREMENT:**
If your answer does not include citations for every factual statement, it is INCOMPLETE. You MUST:
1. Add inline citations: "([Source Name/URL])" after each factual claim
2. Include a "Sources Cited" section for each sub-question listing all sources with URLs
3. Include a complete "Sources List" at the end with all sources used
4. Ensure every piece of information is traceable to a source

**Compliance Reminder:**
If any information was synthesized from general knowledge, inferences, or common patterns, you MUST state:

> "I can only provide verified information based on the IBM Instana Observability documentation. The information you requested is not available in the provided documentation."

If you need to revise or expand any part, you can return to the appropriate stage."""
        }

        stage_lower = stage.lower() if stage else "complete"
        base_guidance = guidance.get(stage_lower, guidance["complete"])

        if context:
            additional_info = []
            if context.get("sub_questions"):
                additional_info.append("\n**Your sub-questions:**\n" + "\n".join(f"- {q}" for q in context["sub_questions"]))
            if context.get("sources_count"):
                additional_info.append(f"\n**Sources found:** {context['sources_count']}")
            if context.get("gaps"):
                additional_info.append("\n**Gaps identified:**\n" + "\n".join(f"- {g}" for g in context["gaps"]))

            if additional_info:
                base_guidance += "\n" + "\n".join(additional_info)

        return base_guidance

    def _format_resources_list(self, resources: List[Dict[str, Any]]) -> str:
        """Format the list of available resources for display"""
        if not resources:
            return "No resources available."

        formatted = []
        for i, resource in enumerate(resources, 1):
            name = resource.get("name", "Unknown")
            description = resource.get("description", "")
            uri = resource.get("uri", "")
            mime_type = resource.get("mime_type", "")
            tags = resource.get("tags", [])

            resource_str = f"{i}. **{name}**"
            if description:
                resource_str += f"\n   Description: {description}"
            if uri:
                resource_str += f"\n   URI: {uri}"
            if mime_type:
                resource_str += f"\n   MIME Type: {mime_type}"
            if tags:
                resource_str += f"\n   Tags: {', '.join(tags)}"

            formatted.append(resource_str)

        return "\n\n".join(formatted)

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
            # Extract parameters - handle both camelCase and snake_case, following sequential_thinking_tool pattern
            # Try multiple possible parameter name variations
            question = (
                arguments.get("question") or 
                arguments.get("Question") or
                arguments.get("mainQuestion") or
                arguments.get("main_question") or
                ""
            )
            if isinstance(question, str):
                question = question.strip()
            else:
                question = ""

            # Derive question from search_query if question is not provided
            search_query = (
                arguments.get("search_query") or 
                arguments.get("searchQuery") or
                arguments.get("search") or
                ""
            )
            if isinstance(search_query, str):
                search_query = search_query.strip()
            else:
                search_query = ""

            # If question is still empty, use search_query as question
            if not question and search_query:
                question = search_query
                logger.info(f"Using search_query as question: {question}")

            # If still no question, try to derive from context or use default
            if not question:
                # Try to get from sub_questions if available
                sub_questions = arguments.get("sub_questions") or arguments.get("subQuestions") or []
                if sub_questions and isinstance(sub_questions, list) and len(sub_questions) > 0:
                    # Use first sub-question as main question context
                    question = f"Research question related to: {sub_questions[0]}"
                    logger.info(f"Derived question from sub_questions: {question}")
                else:
                    # Use a generic question if nothing is provided
                    question = "General documentation search"
                    logger.warning("No question or search_query provided, using default question")

            stage = (
                arguments.get("stage") or 
                arguments.get("Stage") or
                "complete"
            )
            if isinstance(stage, str):
                stage = stage.strip().lower()
            else:
                stage = "complete"

            max_results = arguments.get("max_results") or arguments.get("maxResults") or arguments.get("max_results") or 5
            if not isinstance(max_results, int):
                try:
                    max_results = int(max_results)
                except (ValueError, TypeError):
                    max_results = 5
            max_results = min(max(1, max_results), 10)  # Clamp between 1 and 10

            additional_context = (
                arguments.get("additional_context") or 
                arguments.get("additionalContext") or
                arguments.get("context") or
                None
            )

            # Extract context information if provided - handle both naming conventions
            context = {}
            sub_questions = arguments.get("sub_questions") or arguments.get("subQuestions") or []
            if sub_questions:
                context["sub_questions"] = sub_questions if isinstance(sub_questions, list) else [sub_questions]
            
            sources_count = arguments.get("sources_count") or arguments.get("sourcesCount")
            if sources_count is not None:
                context["sources_count"] = sources_count
            
            gaps = arguments.get("gaps") or arguments.get("Gaps")
            if gaps:
                context["gaps"] = gaps if isinstance(gaps, list) else [gaps]

            # Get available resources (for guidance only - no automatic search, like sequential thinking)
            available_resources = await self._get_available_resources()
            logger.info(f"Available resources: {available_resources}")
            # Generate guidance for the current stage
            guidance = await self._generate_stage_guidance(stage, question, context if context else None)

            # Add guidance about using URL tools for additional searches
            guidance += "\n\n**Additional Tools Available:**\n"
            guidance += "- Use available URL tools to fetch content from resource URIs\n"
            guidance += "- Use search tools from connected MCP servers to find additional documentation\n"
            
            # Add the actual list of available resources
            if available_resources:
                guidance += "\n\n**Available Resources from MCP Server:**\n\n"
                guidance += self._format_resources_list(available_resources)
                guidance += "\n\n**Instructions:**\n"
                guidance += "- Review the resources listed above\n"
                guidance += "- Use URL tools to fetch content from the resource URIs\n"
                guidance += "- Use these resources to find answers to your sub-questions\n"
            else:
                guidance += "\n\n**Note:** No resources are currently available from MCP servers. Use available search tools or URL tools to find documentation.\n"
            
            # Add additional context if provided
            if additional_context:
                guidance += f"\n\n**Additional Context:**\n{additional_context}"

            # Determine next stage
            stage_flow = {
                "planning": "citation",
                "citation": "summarization",
                "summarization": "complete",
                "complete": None
            }
            next_stage = stage_flow.get(stage.lower(), "citation")

            # Create response (similar structure to sequential thinking - guidance-focused)
            response = {
                "stage": stage.lower(),
                "mainQuestion": question,
                "guidance": guidance,
                "nextStage": next_stage,
                "availableResources": available_resources if available_resources else [],
                "resourceCount": len(available_resources) if available_resources else 0,
                "status": "success"
            }
            logger.info(f"Response: {response}")
            # Add search query hint if provided (for reference, but no search performed)
            if search_query:
                response["suggestedSearchQuery"] = search_query
                response["guidance"] += f"\n\n**Note:** A search query was provided ('{search_query}'), but you should use available URL tools or MCP server search tools to perform the actual search."

            question_display = question[:50] + "..." if len(question) > 50 else question
            logger.info(f"IBM document search guidance provided - Stage: {stage}, Question: {question_display} and response {response}")

            return ToolResult(content=[TextContent(type="text", text=json.dumps(response, indent=2))])

        except ValueError as e:
            logger.error(f"Validation error in IBM document search: {e}")
            # Try to extract question from arguments using multiple possible keys
            main_question = (
                arguments.get("question") or 
                arguments.get("Question") or
                arguments.get("mainQuestion") or
                arguments.get("main_question") or
                arguments.get("search_query") or
                arguments.get("searchQuery") or
                ""
            )
            if isinstance(main_question, str):
                main_question = main_question.strip()
            else:
                main_question = ""
            
            error_response = {
                "stage": "error",
                "mainQuestion": main_question,
                "guidance": f"Validation Error: {str(e)}",
                "nextStage": None,
                "status": "validation_error",
                "error": str(e)
            }
            return ToolResult(content=[TextContent(type="text", text=json.dumps(error_response, indent=2))])

        except Exception as e:
            logger.error(f"Unexpected error in IBM document search: {e}")
            # Try to extract question from arguments using multiple possible keys
            main_question = (
                arguments.get("question") or 
                arguments.get("Question") or
                arguments.get("mainQuestion") or
                arguments.get("main_question") or
                arguments.get("search_query") or
                arguments.get("searchQuery") or
                ""
            )
            if isinstance(main_question, str):
                main_question = main_question.strip()
            else:
                main_question = ""
            
            error_response = {
                "stage": "error",
                "mainQuestion": main_question,
                "guidance": f"An unexpected error occurred: {str(e)}",
                "nextStage": None,
                "status": "failed",
                "error": str(e)
            }
            return ToolResult(content=[TextContent(type="text", text=json.dumps(error_response, indent=2))])
