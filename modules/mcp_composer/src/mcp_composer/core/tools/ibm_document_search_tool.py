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
                    "description": "Main research question to investigate.",
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
                    "default": "planning"
                },
                "sub_questions": {
                    "type": "array",
                    "description": "List of sub-questions you've identified (for planning stage).",
                    "items": {
                        "type": "string"
                    }
                },
                "sources": {
                    "type": "array",
                    "description": "List of sources found (for citation stage).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "summary": {"type": "string"},
                            "content": {"type": "string"}
                        }
                    }
                },
                "findings": {
                    "type": "array",
                    "description": "Summary of findings for each sub-question (for summarization stage).",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sub_question": {"type": "string"},
                            "summaries": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "source": {"type": "string"},
                                        "points": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "additional_context": {
                    "type": "string",
                    "description": "Extra guidance or constraints for the research."
                },
                "search_query": {
                    "type": "string",
                    "description": "Optional search query to perform web search using DuckDuckGo. If provided, the tool will search and return results.",
                    "minLength": 1
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (default: 5, max: 10).",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5
                }
            },
            "required": [
                "question"
            ],
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
    2-3 sub-questions, finding relevant sources from IBM Instana Observability
    documentation, and synthesizing findings with proper citations.
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
        description = """You are a **document search assistant** designed to find accurate and well-supported answers using online sources, including the website provided via resources available in the mcp server using list_resources() method.

**⚠️ MANDATORY: ALL ANSWERS MUST INCLUDE CITATIONS**
- Every factual statement must be followed by a citation: "([Source Name/URL])"
- Every answer must include a "Sources Cited" section
- No information should be provided without citing the source
- An answer without citations is incomplete

For each user message you response after performing the **three sequential stages**:

1. Planning
2. Citation
3. Summarization (WITH CITATIONS - MANDATORY)

---

### ⚙️ General Guardrails - STRICT ENFORCEMENT

**CRITICAL RULES - MUST FOLLOW:**

1. **ONLY use information from the provided documentation URL** - Do NOT use general knowledge, common patterns, logical inferences, or prior knowledge about IBM products.

2. **NO SYNTHESIS FROM GENERAL KNOWLEDGE** - Do NOT combine information from:
   - General knowledge about IBM's observability products
   - Common integration patterns you may know
   - Logical inferences about how products work
   - Prior experience with similar products

3. **ONLY cite actual sources** - Every piece of information MUST come directly from a cited source in the provided documentation. If you cannot find it in the documentation, state: "This information is not available in the provided documentation."

4. **NO ASSUMPTIONS** - Do NOT make assumptions or generate content not explicitly stated in the source material. If information is missing, explicitly state: "This information could not be found in the provided documentation."

5. **NO INFERENCES** - Do NOT infer how products work together, what features exist, or how integrations function based on general knowledge. Only state what is explicitly documented.

6. **STRICT SOURCE REQUIREMENT** - Every factual claim must be traceable to a specific cited source with URL. If you cannot cite a source, do not include the information.

7. **OBJECTIVE TONE ONLY** - Keep the tone objective, professional, and factual — no opinions, speculation, or educated guesses.

8. **NO EXTERNAL SOURCES** - Do NOT include information from sources outside the approved documentation URL(s).

### 🧭 1. Planning

**Goal:** Break down the user's question into 2–3 precise, self-contained sub-questions that together address the user's query completely.

**Instructions:**
- Carefully analyze the user's main question.
- Identify key aspects, dimensions, or unknowns that need to be explored.
- Formulate 2–3 sub-questions that are clear, factual, and non-overlapping.
- Ensure each sub-question could independently be answered by a search.

**Response format:**
```markdown
**Main Question:** <restate the user's question>

**Subquestions:**

1. ...
2. ...
3. ...
```

### 📚 2. Citation

**Goal:** For each sub-question, find the most relevant sources using the provided website URL or search tool.

**Instructions:**
- Use the entire sub-question or a focused search term when retrieving sources.
- Select the most authoritative and relevant materials from the website.
- For each source, extract:
  - Title
  - URL
  - Short summary of relevance
  - Full content (or a short excerpt if the full text isn't available)

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

### 📝 3. Summarization

**Goal:** Synthesize information from the gathered sources into concise, accurate summaries that directly answer each sub-question.

**CRITICAL: ALWAYS INCLUDE CITATIONS**
- **Every answer MUST include citations** - No information should be provided without citing the source
- **Every bullet point MUST reference its source** with the source name/URL
- **Citations are mandatory** - If you cannot cite a source, do not include that information

**Instructions:**
- Focus ONLY on information explicitly stated in the cited sources
- Summarize key insights from each source in 2–4 concise bullet points
- **ALWAYS cite the source** for each piece of information provided
- Do NOT add information from general knowledge or make inferences
- If a source doesn't contain the information needed, state that explicitly
- Avoid redundancy and ensure factual neutrality
- Every bullet point must be directly traceable to the cited source with URL

**Response format:**
```markdown
### Subquestion: ...

**Answer:**
[Your summary answer here, with inline citations like: "According to [Source Name/URL], ..."]

**Sources Cited:**
- **Source 1:** [Source Name] - [URL]
  - [Key point 1 from this source]
  - [Key point 2 from this source]
  - [Key point 3 from this source]

- **Source 2:** [Source Name] - [URL]
  - [Key point 1 from this source]
  - [Key point 2 from this source]
  - [Key point 3 from this source]
```

**IMPORTANT:** Every factual statement in your answer must be followed by a citation in the format: "([Source Name/URL])" or clearly linked to a source in the Sources Cited section.

### Final Notes

- **CITATIONS ARE MANDATORY** - Every answer must include citations. No information should be provided without citing the source.
- **ONLY use information explicitly found in the provided documentation**
- **Do NOT use general knowledge or make logical inferences**
- Maintain an objective and evidence-based tone throughout
- **Every claim MUST be followed by a citation** - Format: "([Source Name/URL])" or clearly reference the source
- Ensure all claims are traceable to a specific cited source with URL
- Do NOT invent, infer, or synthesize information from general knowledge
- If information is missing, explicitly state: "This information could not be found in the provided documentation"
- If you find yourself using general knowledge or making inferences, STOP and state that the information is not available in the documentation
- **Remember: An answer without citations is incomplete and violates the guardrails**

### 🚦 Compliance Reminder

**If at any point:**
- You cannot find information in the provided documentation
- You are tempted to use general knowledge or make inferences
- The user request goes beyond the scope of the provided sources
- You would need to synthesize information from general knowledge

**You MUST respond with:**

> "I can only provide verified information based on the IBM Instana Observability documentation. The information you requested is not available in the provided documentation."

**DO NOT:**
- Fill gaps with general knowledge
- Make logical inferences about how things work
- Synthesize information from common patterns
- Use prior knowledge about IBM products

**Parameters:**
- **question**: Your main document search question (required)
- **stage**: Current document search stage you're working on ('planning', 'citation', 'summarization', or 'complete')
- **search_query**: Optional search query to search within available resources. If provided, the tool will search through the resources list and return matching results.
- **max_results**: Maximum number of search results to return (default: 5, max: 10)
- **sub_questions**: List of sub-questions you've identified (for planning stage)
- **sources**: List of sources you've found (for citation stage)
- **findings**: Summary of findings for each sub-question (for summarization stage)
- **additional_context**: Extra guidance or constraints for the document search

**Resource Search:**
This tool searches within available resources from the MCP server. To search, provide the `search_query` parameter along with your question. The tool will search through the resources list and return matching resources with names, URIs, descriptions, and tags that you can use as sources for your document search.

Remember: This tool provides guidance, structure, and resource search capabilities. Use the search_query parameter to find relevant resources from the available documentation sources, then organize and synthesize your document search following the 3-stage workflow."""

        # Get tool name from config or use default
        tool_name = "ibmdocumentsearch"
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

**Your task:** For each sub-question, find the most relevant sources using the available resources or search tool.

**CRITICAL RULES:**
- **ONLY use sources from the provided IBM Instana Observability documentation**
- **Use available resources from list_resources() - see list below**
- **Do NOT use general knowledge, common patterns, or logical inferences**
- **Do NOT synthesize information from general knowledge about IBM products**
- If you cannot find a source in the documentation, state: "No source found in the provided documentation"

**Available Resources:**
{resources_list_text}

**Guidelines:**
- **First, check the available resources listed above** - these are documentation sources you can access
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
1. Search using relevant keywords from the sub-question
2. Review search results for relevance to IBM Instana documentation
3. Select the most relevant sources
4. Record source information in the required format

**Next steps:**
1. Search for sources for each sub-question
2. Compile your source list with proper citations
3. Once you have sources for all sub-questions, move to Stage 3: Summarization""",

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

**CRITICAL COMPLIANCE CHECK:**
Before finalizing, verify:
- **Did I include citations for EVERY factual statement?**
- **Does my answer have a "Sources Cited" section?**
- Did I use ONLY information from the provided documentation?
- Did I avoid using general knowledge about IBM products?
- Did I avoid making logical inferences?
- Did I avoid synthesizing from common patterns?
- Can every claim be traced to a specific cited source with URL?

**CITATION REQUIREMENT:**
If your answer does not include citations for every factual statement, it is INCOMPLETE. You MUST:
1. Add inline citations: "([Source Name/URL])" after each factual claim
2. Include a "Sources Cited" section listing all sources with URLs
3. Ensure every piece of information is traceable to a source

**Compliance Reminder:**
If any information was synthesized from general knowledge, inferences, or common patterns, you MUST state:

> "I can only provide verified information based on the IBM Instana Observability documentation. The information you requested is not available in the provided documentation."

If you need to revise or expand any part, you can return to the appropriate stage."""
        }

        stage_lower = stage.lower() if stage else "planning"
        base_guidance = guidance.get(stage_lower, guidance["planning"])

        if context:
            additional_info = []
            if context.get("sub_questions"):
                additional_info.append(f"\n**Your sub-questions:**\n" + "\n".join(f"- {q}" for q in context["sub_questions"]))
            if context.get("sources_count"):
                additional_info.append(f"\n**Sources found:** {context['sources_count']}")
            if context.get("gaps"):
                additional_info.append(f"\n**Gaps identified:**\n" + "\n".join(f"- {g}" for g in context["gaps"]))
            
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
        try:
            # Extract parameters
            question = arguments.get("question", "").strip()
            if not question:
                raise ValueError("Document search question is required")

            stage = arguments.get("stage", "planning")
            search_query = arguments.get("search_query", "").strip()
            max_results = arguments.get("max_results", 5)
            additional_context = arguments.get("additional_context")
            
            # Extract context information if provided
            context = {}
            if "sub_questions" in arguments:
                context["sub_questions"] = arguments["sub_questions"]
            if "sources_count" in arguments:
                context["sources_count"] = arguments["sources_count"]
            if "gaps" in arguments:
                context["gaps"] = arguments["gaps"]

            # Get available resources
            available_resources = await self._get_available_resources()
            
            # Search resources if search_query is provided
            search_results = []
            if search_query:
                search_results = await self._search_resources(search_query, max_results)
                logger.info(f"Searched resources for: '{search_query}' - found {len(search_results)} results")

            # Generate guidance for the current stage
            guidance = await self._generate_stage_guidance(stage, question, context if context else None)

            # Add search results to guidance if available
            if search_results:
                guidance += f"\n\n**Resource Search Results for '{search_query}':**\n\n"
                for i, result in enumerate(search_results, 1):
                    guidance += f"{i}. **{result['title']}**\n"
                    guidance += f"   URI: {result['url']}\n"
                    if result.get('snippet'):
                        guidance += f"   Description: {result['snippet'][:200]}...\n"
                    if result.get('mime_type'):
                        guidance += f"   MIME Type: {result['mime_type']}\n"
                    if result.get('tags'):
                        guidance += f"   Tags: {', '.join(result['tags'])}\n"
                    guidance += "\n"
                guidance += "Use these resources from the available documentation sources. Evaluate each resource for relevance to your sub-questions."

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

            # Create response
            response = {
                "stage": stage.lower(),
                "mainQuestion": question,
                "guidance": guidance,
                "nextStage": next_stage,
                "status": "success"
            }

            # Add search results to response if available
            if search_results:
                response["searchResults"] = search_results
                response["searchQuery"] = search_query

            # Add available resources to response
            if available_resources:
                response["availableResources"] = available_resources

            logger.info(f"IBM document search guidance provided - Stage: {stage}, Question: {question[:50]}...")

            return ToolResult(content=[TextContent(type="text", text=json.dumps(response, indent=2))])

        except ValueError as e:
            logger.error(f"Validation error in IBM document search: {e}")
            error_response = {
                "stage": "error",
                "mainQuestion": arguments.get("question", ""),
                "guidance": f"Validation Error: {str(e)}",
                "nextStage": None,
                "status": "validation_error",
                "error": str(e)
            }
            return ToolResult(content=[TextContent(type="text", text=json.dumps(error_response, indent=2))])

        except Exception as e:
            logger.error(f"Unexpected error in IBM document search: {e}")
            error_response = {
                "stage": "error",
                "mainQuestion": arguments.get("question", ""),
                "guidance": f"An unexpected error occurred: {str(e)}",
                "nextStage": None,
                "status": "failed",
                "error": str(e)
            }
            return ToolResult(content=[TextContent(type="text", text=json.dumps(error_response, indent=2))])
