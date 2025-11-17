# deep_research_tool.py

import json
from typing import Dict, Any, Optional, List
from pathlib import Path

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

from mcp_composer.core.utils import LoggerFactory, load_json_sync

logger = LoggerFactory.get_logger()


def load_deep_research_schema() -> Dict[str, Any]:
    """Load the deep research tool parameter schema from JSON resource file"""
    try:
        # Get the current file's directory and navigate to resources
        current_dir = Path(__file__).parent
        # Navigate up to the project root and then to resources
        schema_path = current_dir.parent.parent.parent.parent / "resources" / "schemas" / "deep_research_tool_schema.json"

        if not schema_path.exists():
            logger.warning(f"Schema file not found at {schema_path}, using fallback schema")
            return _get_fallback_schema()

        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
            logger.info(f"Loaded deep research schema from {schema_path}")
            return schema

    except Exception as e:
        logger.error(f"Error loading deep research schema: {e}")
        logger.info("Using fallback schema")
        return _get_fallback_schema()


def _get_fallback_schema() -> Dict[str, Any]:
    """Fallback schema if JSON file cannot be loaded"""
    fallback_json_file_path = Path(__file__).parent / "deep_research_tool_fallback_schema.json"
    return load_json_sync(fallback_json_file_path)


class DeepResearchTool(Tool):
    """
    Deep Research Tool for comprehensive research and analysis.
    
    This tool guides you through a structured 5-stage research workflow to perform
    thorough research by systematically breaking down complex questions, finding
    relevant sources, analyzing information, identifying gaps, and synthesizing
    findings into a comprehensive report.
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
        """Initialize the Deep Research Tool"""

        # Load parameters from JSON schema resource
        parameters = load_deep_research_schema()

        # Comprehensive system prompt that guides the agent
        description = """A comprehensive deep research tool that guides you through a structured 5-stage research workflow.

**Research Workflow - Follow These Stages:**

**Stage 1: Planning**
Break down your main research question into 3-7 focused sub-questions that together cover the topic comprehensively.
Each sub-question should:
- Be specific and answerable
- Cover different aspects or perspectives
- Build toward answering the main question
- Be independent enough to research separately

Example: For "What are the impacts of AI on employment?"
- What is the current state of AI adoption in various industries?
- What are the positive impacts of AI on job creation and productivity?
- What are the negative impacts of AI on job displacement?
- What are the economic implications of AI-driven automation?
- What are the future trends and predictions for AI and employment?

**Stage 2: Source Finding**
For each sub-question, search for and identify high-quality, relevant sources:
- Use this tool's built-in web search (set search_query parameter) or other available tools
- Find 2-5 sources per sub-question
- Prioritize credible sources (academic, government, reputable organizations)
- Evaluate source relevance and quality
- Document source information (title, URL, author, date)

**Stage 3: Summarization**
For each sub-question, extract and summarize key information from your sources:
- Read and analyze each source
- Extract information directly relevant to the sub-question
- Synthesize findings from multiple sources
- Identify key facts, statistics, and insights
- Note any conflicting information or perspectives

**Stage 4: Review**
Analyze your research coverage for gaps and completeness:
- Check if all sub-questions have sufficient coverage
- Identify missing perspectives or information
- Note any unanswered aspects
- Suggest additional research directions if needed
- Verify source quality and relevance

**Stage 5: Writing**
Synthesize all findings into a comprehensive, well-structured research report:
- Write an executive summary
- Organize findings by sub-question
- Include citations for all sources
- Address identified gaps and limitations
- Provide conclusions and recommendations
- Format with clear sections and headings

**Key Principles:**
- Be systematic: Follow each stage in order
- Be thorough: Don't skip sub-questions or rush through stages
- Be critical: Evaluate source quality and identify gaps
- Be organized: Keep track of sources and findings
- Be comprehensive: Cover multiple perspectives and aspects
- Be accurate: Verify information and cite sources properly

**When to use this tool:**
- Complex research questions requiring multiple sources and perspectives
- Academic or professional research projects
- Market research and competitive analysis
- Policy research and impact analysis
- Literature reviews and knowledge synthesis
- Fact-finding and investigative research
- Document search for products and services

**How to use this tool:**
1. Start by calling this tool with your main research question
2. The tool will provide guidance on your research approach
3. Follow the 5-stage workflow systematically
4. Use other available tools (search, document retrieval, etc.) to find sources
5. Return to this tool as needed for guidance on each stage
6. Complete all stages to produce a comprehensive research report

**Parameters:**
- **question**: Your main research question (required)
- **stage**: Current research stage you're working on ('planning', 'source_finding', 'summarization', 'review', 'writing', or 'complete')
- **search_query**: Optional search query to perform web search using DuckDuckGo. If provided, the tool will search and return results.
- **max_results**: Maximum number of search results to return (default: 5, max: 10)
- **sub_questions**: List of sub-questions you've identified (for planning stage)
- **sources**: List of sources you've found (for source finding stage)
- **findings**: Summary of findings for each sub-question (for summarization stage)
- **gaps**: Any gaps or limitations you've identified (for review stage)
- **report**: Your research report draft (for writing stage)
- **additional_context**: Extra guidance or constraints for the research

**Web Search:**
This tool includes built-in DuckDuckGo web search. To search, provide the `search_query` parameter along with your question. The tool will return search results with titles, URLs, and snippets that you can use as sources for your research.

Remember: This tool provides guidance, structure, and web search capabilities. Use the search_query parameter to find sources, then organize and synthesize your research following the 5-stage workflow."""

        # Get tool name from config or use default
        tool_name = "deepresearch"
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
                logger.info("Deep Research Tool configured with resource manager integration")

        logger.info(f"Deep Research Tool '{tool_name}' initialized")

    async def _search_web(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search the web using DuckDuckGo.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 5, max: 10)
            
        Returns:
            List of search results with title, url, and body
        """
        if not DDGS_AVAILABLE:
            logger.warning("DuckDuckGo search not available - package not installed")
            return []
        
        try:
            max_results = min(max(1, max_results), 10)  # Clamp between 1 and 10
            logger.info(f"Searching DuckDuckGo for: {query} (max_results: {max_results})")
            
            if DDGS is None:
                logger.warning("DuckDuckGo search not available - DDGS is None")
                return []
            
            results = []
            with DDGS() as ddgs:
                for result in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("href", ""),
                        "snippet": result.get("body", "")
                    })
            
            logger.info(f"Found {len(results)} search results")
            return results
            
        except Exception as e:
            logger.error(f"Error performing DuckDuckGo search: {e}")
            return []

    def _generate_stage_guidance(self, stage: str, question: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate guidance for a specific research stage"""
        
        guidance = {
            "planning": f"""**STAGE 1: PLANNING**

Your main research question: {question}

**Your task:** Break this question down into 3-7 focused sub-questions.

**Guidelines:**
- Each sub-question should be specific and answerable
- Cover different aspects: definition, causes, effects, future trends, solutions, etc.
- Ensure sub-questions together comprehensively address the main question
- Make sub-questions independent enough to research separately

**Next steps:**
1. Generate your list of sub-questions
2. Review them to ensure comprehensive coverage
3. Once satisfied, move to Stage 2: Source Finding""",

            "source_finding": """**STAGE 2: SOURCE FINDING**

**Your task:** Find 2-5 high-quality sources for each sub-question.

**Guidelines:**
- Use available search tools (web search, document search, etc.)
- Prioritize credible sources (academic, government, reputable organizations)
- Evaluate relevance and quality before including
- Document: title, URL, author (if available), date (if available)

**For each sub-question:**
1. Search using relevant keywords
2. Review search results for relevance
3. Select the best 2-5 sources
4. Record source information

**Next steps:**
1. Search for sources for each sub-question
2. Compile your source list
3. Once you have sources for all sub-questions, move to Stage 3: Summarization""",

            "summarization": """**STAGE 3: SUMMARIZATION**

**Your task:** Extract and summarize key information from sources for each sub-question.

**Guidelines:**
- Read and analyze each source carefully
- Extract information directly relevant to the sub-question
- Synthesize findings from multiple sources
- Identify key facts, statistics, and insights
- Note any conflicting information or perspectives

**For each sub-question:**
1. Review all sources for that sub-question
2. Extract relevant information
3. Synthesize findings into a coherent summary
4. Note key points, statistics, and insights

**Next steps:**
1. Summarize findings for each sub-question
2. Ensure all sub-questions have summaries
3. Once complete, move to Stage 4: Review""",

            "review": """**STAGE 4: REVIEW**

**Your task:** Analyze research coverage for gaps and completeness.

**Guidelines:**
- Check if all sub-questions have sufficient coverage
- Identify missing perspectives or information
- Note any unanswered aspects
- Verify source quality and relevance
- Suggest additional research if needed

**Review checklist:**
- [ ] All sub-questions have sources and summaries
- [ ] Multiple perspectives are covered
- [ ] Sources are credible and relevant
- [ ] No major gaps in coverage
- [ ] Conflicting information is noted

**Next steps:**
1. Review your research coverage
2. Identify any gaps or limitations
3. Note additional research directions if needed
4. Once satisfied, move to Stage 5: Writing""",

            "writing": """**STAGE 5: WRITING**

**Your task:** Synthesize all findings into a comprehensive research report.

**Report structure:**
1. **Title and Introduction**
   - Main research question
   - Brief overview of approach

2. **Executive Summary**
   - Key findings at a glance
   - Main conclusions

3. **Methodology**
   - Brief description of research approach
   - Number of sub-questions and sources

4. **Key Findings** (organized by sub-question)
   - For each sub-question:
     - Sub-question restated
     - Summary of findings
     - Key sources cited

5. **Gaps and Limitations**
   - Any identified gaps
   - Research limitations

6. **Conclusion**
   - Synthesis of main findings
   - Overall answer to research question

7. **Sources/Citations**
   - Complete list of all sources
   - Properly formatted citations

**Next steps:**
1. Write your comprehensive research report
2. Ensure all sections are included
3. Verify all sources are cited
4. Review for completeness and accuracy
5. Mark research as complete""",

            "complete": """**RESEARCH COMPLETE**

Your research has been completed through all 5 stages. Review your final report to ensure:
- All sub-questions are addressed
- Sources are properly cited
- Report is well-structured and comprehensive
- Conclusions are supported by evidence

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

    async def run(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute the deep research tool.
        
        Args:
            arguments: Tool arguments containing research parameters
            
        Returns:
            ToolResult: Research guidance for the current stage
        """
        try:
            # Extract parameters
            question = arguments.get("question", "").strip()
            if not question:
                raise ValueError("Research question is required")

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

            # Perform web search if search_query is provided
            search_results = []
            if search_query:
                search_results = await self._search_web(search_query, max_results)
                logger.info(f"Performed web search: '{search_query}' - found {len(search_results)} results")

            # Generate guidance for the current stage
            guidance = self._generate_stage_guidance(stage, question, context if context else None)

            # Add search results to guidance if available
            if search_results:
                guidance += f"\n\n**Web Search Results for '{search_query}':**\n\n"
                for i, result in enumerate(search_results, 1):
                    guidance += f"{i}. **{result['title']}**\n"
                    guidance += f"   URL: {result['url']}\n"
                    guidance += f"   Snippet: {result['snippet'][:200]}...\n\n"
                guidance += "Use these sources to inform your research. Evaluate each source for relevance and credibility."

            # Add additional context if provided
            if additional_context:
                guidance += f"\n\n**Additional Context:**\n{additional_context}"

            # Determine next stage
            stage_flow = {
                "planning": "source_finding",
                "source_finding": "summarization",
                "summarization": "review",
                "review": "writing",
                "writing": "complete",
                "complete": None
            }
            next_stage = stage_flow.get(stage.lower(), "source_finding")

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

            logger.info(f"Deep research guidance provided - Stage: {stage}, Question: {question[:50]}...")

            return ToolResult(content=[TextContent(type="text", text=json.dumps(response, indent=2))])

        except ValueError as e:
            logger.error(f"Validation error in deep research: {e}")
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
            logger.error(f"Unexpected error in deep research: {e}")
            error_response = {
                "stage": "error",
                "mainQuestion": arguments.get("question", ""),
                "guidance": f"An unexpected error occurred: {str(e)}",
                "nextStage": None,
                "status": "failed",
                "error": str(e)
            }
            return ToolResult(content=[TextContent(type="text", text=json.dumps(error_response, indent=2))])
